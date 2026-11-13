"""Golden tests on samples/LegacyApp (a synthetic MFC project, no real company code).

Run:  python tests/test_mfcgraph.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core.index import build_index, save_graph, load_graph  # noqa: E402
from mfcgraph_core.lexer import lex, filter_conditionals, STRING, NUMBER, PP, PUNCT  # noqa: E402
from mfcgraph_core.query import (q_search, q_node, q_callers, q_callees, q_impact, q_trace,  # noqa: E402
                                 q_msgmap, q_context, q_diagnose)

passed = 0
failed = 0


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what)
    if detail:
        print("----- output -----\n" + detail + "------------------")


def contains(out, needle, what):
    check(needle in out, "%s  (expected: %s)" % (what, needle), out)


def not_contains(out, needle, what):
    check(needle not in out, "%s  (unexpected: %s)" % (what, needle), out)


def main():
    samples = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "samples", "LegacyApp")

    # ---- lexer unit checks ----
    t = lex("a = R\"x(raw ) string)x\"; b = 1'000; // c\n#define X 1\nL\"w\"", False)
    check(any(k[0] == STRING and k[1] == "raw ) string" for k in t), "lexer: raw string")
    check(any(k[0] == NUMBER and k[1] == "1'000" for k in t), "lexer: C++14 digit separator")
    check(any(k[0] == PP and k[1] == "define X 1" for k in t), "lexer: preprocessor line")
    f, _ = filter_conditionals(lex("#if 0\n{ {\n#endif\nint x;\n#ifdef A\nint a;\n#else\nint b;\n#endif\n", False))
    joined = "".join(k[1] + " " for k in f if k[0] != PP)
    check(joined == "int x ; int a ; ", "lexer: #if 0 skipped, first branch kept", joined)
    rc = lex('CAPTION "Say ""hi"""', True)
    check(len(rc) == 2 and rc[1][1] == 'Say "hi"', "lexer: rc doubled quotes", repr(rc))

    # ---- index the sample project ----
    built = build_index(samples, 1258)
    tmp = os.path.join(tempfile.gettempdir(), "mfcgraph_test_index.mfg")
    save_graph(built, tmp)
    g = load_graph(tmp)
    check(len(g.nodes) == len(built.nodes) and len(g.edges) == len(built.edges), "save/load round trip")

    diag = q_diagnose(g, False)
    contains(diag, "utf16le=1", "UTF-16 .rc detected")
    contains(diag, "ansi:1258=1", "CP1258 source detected")
    contains(diag, "files with unbalanced braces: 0", "#if 0 with unbalanced braces does not break parsing")
    contains(diag, "NOT FOUND 0.0%", "every message-map handler resolved")

    tr = q_trace(g, "Export", 2)
    contains(tr, "Menu IDR_MAINFRAME: File > Export...", "menu caption found")
    contains(tr, "Accelerator Ctrl+E", "accelerator found")
    contains(tr, "handler [ON_COMMAND]: CMainFrame::OnFileExport", "command handler resolved")
    contains(tr, "-> CLegacyDoc::ExportTo", "pDoc->ExportTo resolved through local variable type")
    contains(tr, "CMainFrame::OnUpdateFileExport", "update-UI handler listed")

    dt = q_trace(g, "IDD_EXPORT", 2)
    contains(dt, "class: CExportDlg", "dialog class via enum IDD")
    contains(dt, "IDC_EDIT_PATH  EDITTEXT  <-> DDX_Text m_strPath", "DDX binding")
    contains(dt, "-> OnBnClickedBrowse [ON_BN_CLICKED]", "button handler")
    contains(dt, "Xuất dữ liệu", "Vietnamese caption from UTF-16 .rc")
    contains(dt, "framework entry points: DoDataExchange, OnInitDialog, OnOK", "framework entry points")

    cl = q_callers(g, "CMainFrame::OnRecalcDone", 5)
    contains(cl, "WM_APP_RECALC_DONE [ON_MESSAGE]", "ON_MESSAGE custom message")
    contains(cl, "CLegacyDoc::Recalculate", "PostMessage sender linked (heuristic)")
    cl2 = q_callers(g, "CLegacyDoc::Recalculate", 5)
    contains(cl2, "Menu IDR_MAINFRAME: Tools > Recalculate", "callers reach the menu item")
    contains(cl2, "CLegacyView::OnLButtonDown", "GetDocument()->Recalculate() resolved via return type")
    not_contains(cl2, "OnLButtonDown  LegacyView.cpp:48 [likely]", "GetDocument() resolution is exact")

    z = q_trace(g, "ID_VIEW_ZOOM_150", 1)
    contains(z, "CLegacyView::OnViewZoom", "ON_COMMAND_RANGE covers ids inside the range")
    ra = q_callees(g, "RefreshAny", 1)
    contains(ra, "CMainFrame::Refresh  MainFrm.cpp:90 [ambiguous]", "unknown receiver -> ambiguous candidates")
    contains(ra, "CView::Invalidate", "((CLegacyView*)p)->Invalidate() resolved via cast type")
    ok = q_callees(g, "CExportDlg::OnOK", 1)
    contains(ok, "AfxMessageBox", "Afx* treated as global")
    not_contains(ok, "CDialog::AfxMessageBox", "Afx* not attributed to the base class")
    mm = q_msgmap(g, "CLegacyApp")
    contains(mm, "CWinApp::OnFileNew  [implemented by MFC base class]", "&CWinApp::OnFileNew recognised")

    wn = q_node(g, "util::WriteTextFile", False, 0)
    contains(wn, "Util.cpp:35", "#ifdef _UNICODE branch chosen")

    im = q_impact(g, "CLegacyDoc::ExportCsv", 5)
    contains(im, "CMainFrame::OnFileExport", "impact reaches the handler")
    contains(im, "Menu IDR_MAINFRAME: File > Export...", "impact reaches the UI")
    cx = q_context(g, "CExportDlg::OnOK", 40)
    contains(cx, "Chưa nhập", "CP1258 source decoded in snippets")
    contains(cx, "Overrides CDialog::OnOK", "override of MFC virtual")

    se = q_search(g, "recalc", 20)
    contains(se, "[id] ID_TOOLS_RECALC", "search finds IDs")
    contains(se, "Tools > Recalculate", "search finds menu captions")

    os.remove(tmp)
    print("%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
