"""Preprocessor condition checks (S17: --define / --undef / --undef-unknown).

Run:  python3 tests/test_pp.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core.lexer import lex, filter_conditionals, PP  # noqa: E402
from mfcgraph_core.pp_eval import PPConfig, parse_defines, parse_names  # noqa: E402
from mfcgraph_core.index import build_index, save_graph, load_graph  # noqa: E402
from mfcgraph_core.query import q_diagnose  # noqa: E402

passed = 0
failed = 0


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what + ("\n  " + repr(detail) if detail else ""))


def kept(src, macros=None, stats=None):
    toks, _ = filter_conditionals(lex(src, False), macros, stats)
    return " ".join(t[1] for t in toks if t[0] != PP)


def test_eval():
    m = PPConfig({"FEATURE_X": "1", "LEVEL": "3"}, {"OLD"}).for_file(False)
    cases = [("defined(FEATURE_X)", True), ("!defined OLD", True), ("LEVEL >= 2 && defined(FEATURE_X)", True),
             ("UNKNOWN_M", None), ("0 && UNKNOWN_M", False), ("1 || UNKNOWN_M", True), ("UNKNOWN_M || OLD", None),
             ("_MSC_VER > 1000", True), ("defined(__cplusplus)", True), ("FOO(1, 2)", None),
             ("LEVEL == 3 ? 1 : 0", True), ("(LEVEL + 1) * 2 == 8", True), ("0x10 == 16L", True),
             ("defined(A) /* comment */", None)]
    for expr, want in cases:
        got = m.eval_if(expr)
        check(got is want, "eval %s" % expr, got)
    c = PPConfig({}, (), True).for_file(True)
    check(c.eval_if("defined(__cplusplus)") is False and c.ifdef("_DEBUG") is False, "C file, undef-unknown")
    check(parse_defines("A; B=2 ;") == {"A": "1", "B": "2"} and parse_names("C;D") == {"C", "D"}, "parse options")


def test_filter():
    src = "#ifdef OLD\nold ;\n#else\nnew_code ;\n#endif\n#if LEVEL > 2\nhigh ;\n#elif LEVEL > 1\nmid ;\n#endif\n"
    check(kept(src) == "old ; high ;", "no config: first branch wins", kept(src))
    st = {}
    m = PPConfig({"LEVEL": "2"}, {"OLD"}).for_file(False)
    check(kept(src, m, st) == "new_code ; mid ;", "config: evaluated branches", kept(src, m))
    check(st.get("evaluated") == 3 and not st.get("guessed"), "stats evaluated", st)
    st = {}
    m = PPConfig({"OTHER": "1"}).for_file(False)
    check(kept("#ifdef X\na ;\n#else\nb ;\n#endif\n", m, st) == "a ;" and st.get("guessed") == 1, "unknown -> guessed")
    m = PPConfig({"OTHER": "1"}).for_file(False)
    src2 = "#define LOCAL_ON\n#ifdef LOCAL_ON\non ;\n#endif\n#undef LOCAL_ON\n#ifdef LOCAL_ON\nbad ;\n#else\nok ;\n#endif\n"
    check(kept(src2, m) == "on ; ok ;", "in-file #define/#undef", kept(src2, m))
    src3 = "#ifdef A\n#ifdef B\nab ;\n#else\nanb ;\n#endif\n#else\nna ;\n#endif\n"
    check(kept(src3, PPConfig({"A": "1"}, {"B"}).for_file(False)) == "anb ;", "nested")


def test_malformed():
    src = ("#ifdef (FOO)\na ;\n#endif\n#ifdef /* c */ BAR\nb ;\n#endif\n#ifndef\nc ;\n#endif\n#if\nd ;\n#endif\n"
           "#ifdef\ne ;\n#else\nf ;\n#endif\n")
    st = {}
    out = kept(src, PPConfig({"FOO": "1"}, (), True).for_file(False), st)
    check(out == "a ; c ; d ; e ;", "malformed #ifdef/#if do not crash", out)
    check(kept(src) == "a ; b ; c ; d ; e ;", "malformed, no config")


def test_skip_failing_file():
    from mfcgraph_core import index as idx
    tmp = tempfile.mkdtemp(prefix="mfcgraph_fail_")
    real = idx.extract_cpp
    try:
        for name, body in (("Good.cpp", "void Good() { Bad(); }\n"), ("Bad.cpp", "void Bad() { }\n")):
            with open(os.path.join(tmp, name), "w") as fh:
                fh.write(body)

        def boom(toks, fi, raw):
            if any(t[1] == "Bad" for t in toks[:3]):
                raw.funcs.append(None)  # partial state must be rolled back
                raise IndexError("simulated")
            return real(toks, fi, raw)
        idx.extract_cpp = boom
        import io
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            g = build_index(tmp)
        check("warning: skipped Bad.cpp (IndexError: simulated)" in err.getvalue(), "warning printed", err.getvalue())
        check(g.stats.get("files.failed") == "1" and any(n.name == "Good" for n in g.nodes), "other files indexed")
        check("files skipped because of an internal error: 1" in q_diagnose(g), "diagnose counts skipped files")
    finally:
        idx.extract_cpp = real
        shutil.rmtree(tmp, ignore_errors=True)


def test_index_win32():
    tmp = tempfile.mkdtemp(prefix="mfcgraph_pp_")
    try:
        samples = os.path.join(ROOT, "samples", "Win32App")

        def calls_of(g, name):
            fn = [n.id for n in g.nodes if n.kind == "function" and n.name == name and "decl" not in n.flags]
            return {g.nodes[g.edges[e].dst].name for e in g.out[fn[0]] if g.edges[e].kind == "calls"}
        g0 = build_index(samples, 932)
        check("GetPrivateProfileInt" in calls_of(g0, "LoadOptions"), "default: #ifdef stub branch indexed")
        g1 = build_index(samples, 932, pp=PPConfig({}, {"USE_INI_FILE"}))
        check("RegQueryValueEx" in calls_of(g1, "LoadOptions") and "GetPrivateProfileInt" not in calls_of(g1, "LoadOptions"),
              "--undef USE_INI_FILE: #else (registry) branch indexed", calls_of(g1, "LoadOptions"))
        g2 = build_index(samples, 932, pp=PPConfig({}, (), True))
        check("RegQueryValueEx" in calls_of(g2, "LoadOptions"), "--undef-unknown: #else branch indexed")
        path = os.path.join(tmp, "i.mfg")
        save_graph(g1, path)
        g3 = load_graph(path)
        check(g3.pp_undefs == ["USE_INI_FILE"] and not g3.pp_defines, "config saved in index (D records)")
        d = q_diagnose(g3)
        check("#if conditions: evaluated" in d and "guessed" in d, "diagnose shows #if counts", d)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    test_eval()
    test_filter()
    test_malformed()
    test_skip_failing_file()
    test_index_win32()
    print("pp: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
