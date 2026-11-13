// ExportDlg.cpp : エクスポートダイアログ (メッセージクラッカー使用)
#include "App.h"
#include <windowsx.h>

static DOCUMENT* g_pExportDoc = NULL;

static BOOL Export_OnInitDialog(HWND hwnd, HWND hwndFocus, LPARAM lParam)
{
    g_pExportDoc = (DOCUMENT*)lParam;
    SetDlgItemText(hwnd, IDC_EDIT_PATH, _T("export.csv"));
    return TRUE;
}

static void Export_OnCommand(HWND hwnd, int id, HWND hwndCtl, UINT codeNotify)
{
    TCHAR szPath[MAX_PATH];
    DOCUMENT* pDoc = g_pExportDoc;

    GetDlgItemText(hwnd, IDC_EDIT_PATH, szPath, MAX_PATH);
    switch (id) {
    case IDC_BTN_BROWSE:
        BrowseForFile(hwnd, szPath, MAX_PATH);
        SetDlgItemText(hwnd, IDC_EDIT_PATH, szPath);
        break;
    case IDOK:
        if (!ExportCsv(pDoc, szPath))
            MessageBox(hwnd, _T("エクスポートに失敗しました"), NULL, MB_ICONERROR);
        else
            SetStatusText(_T("Export done"));
        EndDialog(hwnd, IDOK);
        break;
    case IDCANCEL:
        EndDialog(hwnd, IDCANCEL);
        break;
    }
}

INT_PTR CALLBACK ExportDlgProc(HWND hDlg, UINT msg, WPARAM wParam, LPARAM lParam)
{
    switch (msg) {
        HANDLE_MSG(hDlg, WM_INITDIALOG, Export_OnInitDialog);
        HANDLE_MSG(hDlg, WM_COMMAND, Export_OnCommand);
    }
    return FALSE;
}
