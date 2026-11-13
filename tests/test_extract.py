"""Extractor unit checks (v0.2 additions) on samples/LegacyApp.

Run:  python3 tests/test_extract.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core.encoding import decode_bytes  # noqa: E402
from mfcgraph_core.extract_cpp import extract_cpp, clean_literal  # noqa: E402
from mfcgraph_core.lexer import lex, filter_conditionals  # noqa: E402
from mfcgraph_core.model import RawData  # noqa: E402

SAMPLES = os.path.join(ROOT, "samples", "LegacyApp")
passed = 0
failed = 0


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what + ("\n  " + str(detail) if detail else ""))


def extract_text(text):
    raw = RawData()
    active, _ = filter_conditionals(lex(text, False))
    extract_cpp(active, 0, raw)
    return raw


def extract_file(rel):
    with open(os.path.join(SAMPLES, rel), "rb") as fh:
        text, _ = decode_bytes(fh.read(), 1258)
    return extract_text(text)


def func(raw, cls, name):
    for f in raw.funcs:
        if f.is_def and f.cls == cls and f.name == name:
            return f
    return None


def test_strings():
    f = func(extract_file("MainFrm.cpp"), "CMainFrame", "OnFileExport")
    check(f is not None and (69, "Export failed") in f.strings, "S2a: 'Export failed' at line 69 (PLAN says 68; file has 69)",
          f and f.strings)
    check(clean_literal("%d") == "" and clean_literal("\\r\\n") == "" and clean_literal("%s: %d") == "",
          "S2a: format-only strings dropped")
    check(clean_literal("ab") == "" and clean_literal("abc") == "abc", "S2a: < 3 letters dropped")
    check(len(clean_literal("x" * 500)) == 200, "S2a: cut at 200 chars")
    check(clean_literal("Không thể lưu") == "Không thể lưu", "S2a: Vietnamese kept")
    raw = extract_text('void F()\n{\n  Show(_T("abc " "def"),\n   "%d");\n  x = "ghi\\tjkl";\n}\n')
    f = func(raw, "", "F")
    check(f is not None and f.strings == [(3, "abc def"), (5, "ghi\\tjkl")], "S2a: adjacent literals joined",
          f and f.strings)


def test_refs():
    f = func(extract_file("LegacyView.cpp"), "CLegacyView", "OnViewZoom")
    w = [r for r in (f.refs if f else []) if r[0] == "m_nZoom" and r[3] == "w"]
    check(len(w) == 3, "S3a: 3 writes of m_nZoom in OnViewZoom", f and f.refs)
    src = ("void F()\n{\n if (m_a == 1) m_b += 2;\n ++m_c; p->x = 1; d.y; m_arr[i] = 3;\n"
           " Foo(m_z); m_q.Get(); g_n--;\n}\n")
    f = func(extract_text(src), "", "F")
    got = sorted((r[0], r[1], r[3]) for r in f.refs)
    want = sorted([("m_a", "", "r"), ("m_b", "", "w"), ("m_c", "", "w"), ("x", "p", "w"), ("y", "d", "r"),
                   ("m_arr", "", "w"), ("m_z", "", "r"), ("m_q", "", "r"), ("g_n", "", "w")])
    check(got == want, "S3a: read/write modes", got)


def test_c_mode():
    from mfcgraph_core import cmode
    src = ("BOOL DocAddRecord(DOCUMENT* pDoc, const char* line)\n{\n"
           "    struct record *new = (struct record*)malloc(sizeof(*new));\n"
           "    int class = ParseLine(line);\n    new->kind = class;\n    DocLinkRecord(pDoc, new);\n"
           "    return TRUE;\n}\nvoid delete(struct list* this) { free(this); }\n"
           "int template(int x) { return Twice(x); }\n")
    raw = RawData()
    toks, _ = filter_conditionals(lex(src, False))
    toks, n = cmode.protect(toks)
    before = cmode.snapshot(raw)
    extract_cpp(toks, 0, raw)
    cmode.restore(raw, before)
    names = sorted(f.name for f in raw.funcs if f.is_def)
    check(n > 0 and names == ["DocAddRecord", "delete", "template"], "S16: C functions named like C++ keywords", names)
    f = func(raw, "", "DocAddRecord")
    check(f is not None and [c.name for c in f.calls] == ["malloc", "ParseLine", "DocLinkRecord"],
          "S16: calls inside C body", f and [c.name for c in f.calls])
    check(f is not None and ("kind", "new", 5, "w") in f.refs, "S16: new->kind write with receiver 'new'", f and f.refs)
    check(f is not None and f.locals.get("new") == "record", "S16: local named new typed struct record", f and f.locals)
    allnames = repr([(g.name, g.sig, [(c.name, c.recv) for c in g.calls], g.refs, g.locals) for g in raw.funcs])
    check(cmode.MARK not in allnames, "S16: marker fully removed")
    check(cmode.is_c_file("a/b/Doc.c") and not cmode.is_c_file("Doc.cpp") and not cmode.is_c_file("Doc.h"),
          "S16: only .c files")


def main():
    test_strings()
    test_refs()
    test_c_mode()
    print("extract: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
