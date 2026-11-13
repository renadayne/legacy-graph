"""Checks for mfcgraph_core/explore_seed.py on samples/LegacyApp and samples/BigApp.

Run:  python3 tests/test_explore_seed.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core.index import build_index  # noqa: E402
from mfcgraph_core.explore_query import parse_query  # noqa: E402
from mfcgraph_core.explore_seed import seed, segments  # noqa: E402

passed = 0
failed = 0


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what + ("\n  " + repr(detail) if detail else ""))


def run(g, q):
    return seed(g, parse_query(q), (), q)


def top(g, r, k=3):
    order = sorted(r.seeds.items(), key=lambda kv: (-kv[1][0], kv[0]))
    return [g.nodes[n].qname for n, _ in order[:k]]


def qn(g, r):
    return {g.nodes[n].qname for n in r.seeds}


def main():
    check(segments("OnBnClickedRecalc") == ["on", "bn", "clicked", "recalc"], "segments camel")
    check(segments("CExportDlg") == ["c", "export", "dlg"], "segments class prefix", segments("CExportDlg"))

    g = build_index(os.path.join(ROOT, "samples", "LegacyApp"))
    r = run(g, "MainFrm.cpp:69")
    check(top(g, r, 1) == ["CMainFrame::OnFileExport"] and r.exact and r.pinned_files, "anchor -> exact function")
    fe = [n for n in r.seeds][0]
    check(69 in r.focus.get(fe, ()), "anchor line is a focus line")
    r = run(g, "CLegacyDoc::ExportCsv")
    check(top(g, r, 1) == ["CLegacyDoc::ExportCsv"] and len(r.exact) == 1, "qualified exact")
    r = run(g, "ID_FILE_EXPORT")
    check("CMainFrame::OnFileExport" in qn(g, r), "id -> handler", qn(g, r))
    r = run(g, "WM_APP_RECALC_DONE")
    check({"CMainFrame::OnRecalcDone", "CLegacyDoc::Recalculate"} <= qn(g, r), "message id -> handler + sender")
    r = run(g, '"Export failed"')
    check(top(g, r, 1) == ["CMainFrame::OnFileExport"] and r.texts, "quoted literal")
    r = run(g, '"Xuất dữ liệu"')
    check("CExportDlg" in qn(g, r), "quoted dialog caption -> dialog class", qn(g, r))
    r = run(g, "CExportDlg::m_strPath")
    check("CExportDlg::OnBnClickedBrowse" in qn(g, r), "qualified field -> writers", qn(g, r))
    r = run(g, "WriteTextFle")
    check(r.unmatched and "WriteTextFile" in r.suggestions.get("WriteTextFle", []), "did you mean", r.suggestions)
    r = run(g, "CLegacyDoc::Recalc")
    check("CLegacyDoc::Recalculate" in r.suggestions.get("CLegacyDoc::Recalc", []), "did you mean qualified",
          r.suggestions)

    b = build_index(os.path.join(ROOT, "samples", "BigApp"))
    r = run(b, "bấm Tính lại thì tổng tiền sai trong module Billing")
    check(r.scope_dirs == ["Billing"], "module word -> scope dir", r.scope_dirs)
    check("CInvoiceDlg::OnBnClickedRecalc" in top(b, r, 3), "unquoted caption in free text", top(b, r, 5))
    r = run(b, 'thông báo "Không thể lưu hóa đơn" khi bấm OK')
    check(top(b, r, 1) == ["CInvoiceDlg::OnOK"], "literal beats short caption inside the quote", top(b, r, 5))
    check("CInvoiceDlg" not in qn(b, r), "caption 'Hóa đơn' inside quote not matched as free text")
    r = run(b, '"Báo cáo không có dữ liệu"')
    check(top(b, r, 1) == ["CReportBuilder::BuildMonthly"], "string table text -> function using the IDS id")
    r = run(b, "Report/ReportBuilder.cpp RoundTo")
    files = {b.files[b.nodes[n].file].path for n in r.seeds if b.nodes[n].name == "RoundTo"}
    check(files == {"Report/ReportBuilder.cpp"}, "duplicate static: pinned file wins", files)
    r = run(b, "Billing/ discount")
    check(r.scope_dirs == ["Billing"], "path dir -> scope", r.scope_dirs)
    print("explore_seed: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
