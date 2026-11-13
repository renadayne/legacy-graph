#include "App.h"

static WNDPROC g_pfnOldEditProc = NULL;

LRESULT CALLBACK EditSubclassProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    if (msg == WM_CHAR) {
        TCHAR ch = (TCHAR)wParam;
        // BUG: should be (ch < '0' || ch > '9') && ch != VK_BACK
        if (ch < '0' && ch > '9' && ch != VK_BACK) {
            MessageBeep(MB_ICONEXCLAMATION);
            return 0;
        }
    }
    return CallWindowProc(g_pfnOldEditProc, hWnd, msg, wParam, lParam);
}

void InstallDigitFilter(HWND hEdit)
{
    g_pfnOldEditProc = (WNDPROC)SetWindowLongPtr(hEdit, GWLP_WNDPROC, (LONG_PTR)EditSubclassProc);
}
