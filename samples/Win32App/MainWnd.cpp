// MainWnd.cpp : メインウィンドウのウィンドウプロシージャ
#include "MainWnd.h"

// 点滅タイマー (500ms)
VOID CALLBACK BlinkTimerProc(HWND hWnd, UINT uMsg, UINT_PTR idEvent, DWORD dwTime)
{
    static BOOL bOn = FALSE;
    bOn = !bOn;
    SetStatusText(bOn ? _T("*") : _T(" "));
}

// 保存完了通知を受け取る
void OnSaveDone(HWND hWnd, BOOL bOk)
{
    if (bOk)
        SetStatusText(_T("Saved"));
    else
        ShowErrorId(hWnd, IDS_SAVE_FAILED);
}

LRESULT CALLBACK MainWndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    switch (msg) {
    case WM_CREATE:
        // 自動保存タイマーを開始
        SetTimer(hWnd, ID_TIMER_AUTOSAVE, g_options.nInterval * 1000, NULL);
        SetTimer(hWnd, ID_TIMER_BLINK, 500, BlinkTimerProc);
        return 0;

    case WM_COMMAND:
        switch (LOWORD(wParam)) {
        case IDM_FILE_SAVE:
            if (!DocSave(&g_doc))
                ShowErrorId(hWnd, IDS_SAVE_FAILED);
            break;
        case IDM_FILE_EXPORT:
            DialogBoxParam(g_hInst, MAKEINTRESOURCE(IDD_EXPORT), hWnd,
                ExportDlgProc, (LPARAM)&g_doc);
            break;
        case IDM_TOOLS_OPTIONS:
            DialogBox(g_hInst, MAKEINTRESOURCE(IDD_OPTIONS), hWnd, OptionsDlgProc);
            break;
        case IDM_HELP_ABOUT:
            DialogBox(g_hInst, MAKEINTRESOURCE(IDD_ABOUT), hWnd, AboutDlgProc);
            break;
        case IDM_FILE_EXIT:
            DestroyWindow(hWnd);
            break;
        }
        break;

    case WM_TIMER:
        if (wParam == ID_TIMER_AUTOSAVE)
            StartBackgroundSave(hWnd, &g_doc);
        break;

    case WM_APP_SAVE_DONE:
        OnSaveDone(hWnd, (BOOL)wParam);
        break;

    case WM_DESTROY:
        KillTimer(hWnd, ID_TIMER_AUTOSAVE);
        KillTimer(hWnd, ID_TIMER_BLINK);
        PostQuitMessage(0);
        break;

    default:
        return DefWindowProc(hWnd, msg, wParam, lParam);
    }
    return 0;
}
