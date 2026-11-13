// OptionsDlg.cpp : オプションダイアログ
#include "App.h"

// 現在の設定をダイアログに反映する
void LoadOptionsToDialog(HWND hDlg)
{
    CheckDlgButton(hDlg, IDC_CHK_AUTOSAVE, g_options.bAutoSave ? BST_CHECKED : BST_UNCHECKED);
    SetDlgItemInt(hDlg, IDC_EDIT_INTERVAL, g_options.nInterval, FALSE);
}

// ダイアログの内容を設定に保存する
static void ApplyOptions(HWND hDlg)
{
    g_options.nInterval = GetDlgItemInt(hDlg, IDC_EDIT_INTERVAL, NULL, FALSE);
    g_options.bAutoSave = (IsDlgButtonChecked(hDlg, IDC_CHK_AUTOSAVE) == BST_CHECKED);
    SaveOptions(&g_options);
}

INT_PTR CALLBACK OptionsDlgProc(HWND hDlg, UINT msg, WPARAM wParam, LPARAM lParam)
{
    switch (msg) {
    case WM_INITDIALOG:
        LoadOptionsToDialog(hDlg);
        InstallDigitFilter(GetDlgItem(hDlg, IDC_EDIT_INTERVAL));
        return TRUE;

    case WM_COMMAND:
        switch (LOWORD(wParam)) {
        case IDC_BTN_APPLY:
            ApplyOptions(hDlg);
            break;
        case IDOK:
            ApplyOptions(hDlg);
            EndDialog(hDlg, IDOK);
            break;
        case IDCANCEL:
            EndDialog(hDlg, IDCANCEL);
            break;
        }
        return TRUE;
    }
    return FALSE;
}
