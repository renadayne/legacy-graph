"""Unit checks for mfcgraph_core/explore_query.py.

Run:  python3 tests/test_explore_query.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from mfcgraph_core.explore_query import parse_query, Term  # noqa: E402

passed = 0
failed = 0


def T(kind, value, extra=""):
    return Term(kind, value, extra)


CASES = [
    ("Export failed WriteTextFile", [T("word", "export"), T("ident", "WriteTextFile")]),
    ("MainFrm.cpp:68", [T("anchor", "MainFrm.cpp", (68, 68))]),
    ("Billing\\InvoiceDlg.cpp:100-140", [T("anchor", "Billing/InvoiceDlg.cpp", (100, 140))]),
    ("Billing/InvoiceDlg.cpp:88 tổng tiền", [T("anchor", "Billing/InvoiceDlg.cpp", (88, 88)), T("word", "tổng"),
                                            T("word", "tiền")]),
    ("bug in Billing/", [T("path", "Billing", "dir")]),
    ("Report\\Common", [T("path", "Report/Common", "dir")]),
    ("look at InvoiceDlg.cpp", [T("path", "InvoiceDlg.cpp", "file")]),
    ("CLegacyDoc::ExportCsv", [T("qualified", "CLegacyDoc::ExportCsv")]),
    ("CLegacyDoc.ExportCsv crashes", [T("qualified", "CLegacyDoc::ExportCsv"), T("word", "crashes")]),
    ("util::WriteTextFile and ::GlobalFn", [T("qualified", "util::WriteTextFile"), T("qualified", "GlobalFn")]),
    ("ID_FILE_EXPORT", [T("id", "ID_FILE_EXPORT")]),
    ("IDD_EXPORT dialog, WM_APP_RECALC_DONE", [T("id", "IDD_EXPORT"), T("word", "dialog"),
                                               T("id", "WM_APP_RECALC_DONE")]),
    ('thông báo "Không thể lưu hóa đơn"', [T("word", "thông"), T("word", "báo"),
                                          T("quoted", "Không thể lưu hóa đơn")]),
    ("message 'Export failed' shown", [T("word", "message"), T("quoted", "Export failed"), T("word", "shown")]),
    ("it doesn't save", [T("word", "doesn"), T("word", "save")]),
    ("m_nZoom wrong after zoom", [T("ident", "m_nZoom"), T("word", "zoom")]),
    ("LOG_ERROR in OnBnClickedSave", [T("ident", "LOG_ERROR"), T("ident", "OnBnClickedSave")]),
    ("bấm Tính lại thì tổng tiền sai trong module Billing",
     [T("word", "tính"), T("word", "tổng"), T("word", "tiền"), T("word", "billing")]),
    ("“Không tìm thấy khách hàng”", [T("quoted", "Không tìm thấy khách hàng")]),
    ("Export... menu", [T("word", "export"), T("word", "menu")]),
    ("export export Export", [T("word", "export")]),
    ("", []),
    ("CExportDlg OnOK", [T("ident", "CExportDlg"), T("ident", "OnOK")]),
]


def main():
    global passed, failed
    for q, want in CASES:
        got = parse_query(q)
        if got == want:
            passed += 1
        else:
            failed += 1
            print("FAIL: %r\n  want %r\n  got  %r" % (q, want, got))
    # NFD input is normalised to NFC
    nfd = parse_query("tiền")
    if nfd == [T("word", "tiền")]:
        passed += 1
    else:
        failed += 1
        print("FAIL: NFC normalisation", nfd)
    print("explore_query: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
