#include "App.h"

static TCHAR s_szStatus[128];

void SetStatusText(LPCTSTR pszText)
{
    lstrcpyn(s_szStatus, pszText, 128);
}

void ShowErrorId(HWND hWnd, UINT nId)
{
    TCHAR szMsg[256];

    if (LoadString(g_hInst, nId, szMsg, 256) == 0)
        lstrcpy(szMsg, _T("Error"));
    MessageBox(hWnd, szMsg, _T("Win32App"), MB_ICONERROR | MB_OK);
}
