"""Win32 dispatch checks (S18+) on samples/Win32App (index with codepage 932).

Run:  python3 tests/test_win32.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core.index import build_index  # noqa: E402
from mfcgraph_core.lexer import lex, filter_conditionals  # noqa: E402
from mfcgraph_core.extract_cpp import extract_cpp  # noqa: E402
from mfcgraph_core.model import RawData  # noqa: E402
from mfcgraph_core.explore import explore  # noqa: E402
from mfcgraph_core.query import q_diagnose  # noqa: E402

SAMPLES = os.path.join(ROOT, "samples", "Win32App")
passed = 0
failed = 0


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what + ("\n  " + repr(detail) if detail else ""))


def node(g, name):
    for n in g.nodes:
        if n.kind in ("function", "id") and n.name == name and "decl" not in n.flags.split(","):
            return n
    return None


def edges(g, src_name, kind):
    s = node(g, src_name)
    return [(g.nodes[g.edges[e].dst].name, g.edges[e].line, g.edges[e].extra) for e in g.out[s.id]
            if g.edges[e].kind == kind] if s else []


def test_extract_cases():
    src = ("LRESULT CALLBACK WndProc(HWND h, UINT msg, WPARAM wp, LPARAM lp)\n{\n"
           "  switch (msg) {\n  case WM_COMMAND:\n    switch (LOWORD(wp)) {\n    case IDM_A:\n      DoA();\n"
           "      break;\n    case IDM_B: DoB(); break;\n    default: break;\n    }\n    break;\n"
           "  case WM_DESTROY:\n    PostQuitMessage(0);\n    break;\n  }\n"
           "  HANDLE_MSG(h, WM_SIZE, OnSize);\n  return 0;\n}\n")
    raw = RawData()
    toks, _ = filter_conditionals(lex(src, False))
    extract_cpp(toks, 0, raw)
    f = [x for x in raw.funcs if x.name == "WndProc"][0]
    check(("IDM_A", 6, 8, "WM_COMMAND") in f.cases, "S18: case section with parent", f.cases)
    check(("IDM_B", 9, 9, "WM_COMMAND") in f.cases, "S18: one-line case", f.cases)
    check(any(c[0] == "WM_COMMAND" and c[1] == 4 and c[3] == "" for c in f.cases), "S18: outer case", f.cases)
    check(any(c[0] == "WM_DESTROY" for c in f.cases), "S18: second outer case")
    check(f.crackers == [("WM_SIZE", "OnSize", 17)], "S18: HANDLE_MSG", f.crackers)


def test_graph(g):
    h = edges(g, "IDM_FILE_SAVE", "handled_by")
    check(any(d == "MainWndProc" and x.startswith("case@") for d, _, x in h), "S18: IDM_FILE_SAVE handled by MainWndProc", h)
    cc = [d for d, _, _ in edges(g, "IDM_FILE_SAVE", "case_calls")]
    check("DocSave" in cc and "ShowErrorId" in cc and "ExportDlgProc" not in cc, "S18: calls inside the case only", cc)
    check("win32-proc" in node(g, "MainWndProc").flags and "win32-proc" in node(g, "OptionsDlgProc").flags,
          "S18: win32-proc flag")
    h = [d for d, _, x in edges(g, "WM_COMMAND", "handled_by") if x.startswith("HANDLE_MSG")]
    check("Export_OnCommand" in h, "S18: HANDLE_MSG(WM_COMMAND, Export_OnCommand)", h)
    check("msg-handler" in node(g, "Export_OnCommand").flags, "S18: cracker handler flagged")
    h = [d for d, _, _ in edges(g, "IDC_BTN_APPLY", "handled_by")]
    check("OptionsDlgProc" in h, "S18: dialog button case", h)
    h = [d for d, _, _ in edges(g, "WM_APP_SAVE_DONE", "handled_by")]
    check("MainWndProc" in h, "S18: WM_APP message case", h)
    d = q_diagnose(g)
    check("window/dialog procedures 5" in d, "S18: diagnose win32 line", [x for x in d.splitlines() if "win32" in x])


def test_explore(g):
    out = explore(g, "IDM_FILE_SAVE")
    flow = out.split("## Source")[0]
    check("保存(S)" in flow and "-> MainWndProc  MainWnd.cpp:21" in flow and "-> DocSave" in flow,
          "S18: flow menu -> proc -> DocSave", flow)
    check("エクスポート" not in flow, "S18: flow shows only the UI of the asked id", flow)
    case_line = [ln for ln in out.splitlines() if ln.endswith("case IDM_FILE_SAVE:")]
    check(case_line, "S18: source shows the case line", out[:1500])


def test_wiring(g):
    cb = {(a, d) for a, d in [(g.nodes[e.src].name, g.nodes[e.dst].name) for e in g.edges if e.kind == "callback"]}
    for pair in [("RegisterMainClass", "MainWndProc"), ("MainWndProc", "BlinkTimerProc"),
                 ("StartBackgroundSave", "SaveThreadProc"), ("InstallDigitFilter", "EditSubclassProc"),
                 ("MainWndProc", "ExportDlgProc")]:
        check(pair in cb, "S19: callback %s -> %s" % pair, sorted(cb))
    ud = {(g.nodes[e.src].name, g.nodes[e.dst].name) for e in g.edges if e.kind == "uses_dialog"}
    check(("ExportDlgProc", "IDD_EXPORT") in ud and ("OptionsDlgProc", "IDD_OPTIONS") in ud, "S19: proc uses dialog", ud)
    cc = [d for d, _, _ in edges(g, "IDM_FILE_EXPORT", "case_calls")]
    check("ExportDlgProc" in cc, "S19: dialog started in case IDM_FILE_EXPORT", cc)
    b = build_index(os.path.join(ROOT, "samples", "BigApp"))
    bcb = sorted((b.nodes[e.src].qname, b.nodes[e.dst].qname) for e in b.edges if e.kind == "callback")
    check(bcb == [("CPaymentWorker::Start", "PaymentThreadProc")], "S19: no false callbacks (RUNTIME_CLASS, ctors)", bcb)


def test_explore_wiring(g):
    flow = explore(g, "IDM_FILE_EXPORT").split("## Source")[0]
    check("エクスポート(E)" in flow and "保存" not in flow and "-> ExportDlgProc" in flow, "S19: flow menu -> dialog proc", flow)
    out = explore(g, '"エクスポートに失敗しました"')
    check("### Export.c" in out, "S19: function called just before the message gets code", out[:2000])
    blast = out.split("## Blast radius")[1].split("##")[0]
    check("IDD_OPTIONS" not in blast and "IDD_ABOUT" not in blast, "S19: shared IDOK limited to this dialog", blast)


def main():
    test_extract_cases()
    g = build_index(SAMPLES, 932)
    test_graph(g)
    test_explore(g)
    test_wiring(g)
    test_explore_wiring(g)
    print("win32: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
