#include "App.h"
#include <commdlg.h>

BOOL BrowseForFile(HWND hWnd, LPTSTR pszPath, int cch)
{
    OPENFILENAME ofn;

    ZeroMemory(&ofn, sizeof(ofn));
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner   = hWnd;
    ofn.lpstrFilter = _T("CSV (*.csv)\0*.csv\0All (*.*)\0*.*\0");
    ofn.lpstrFile   = pszPath;
    ofn.nMaxFile    = cch;
    ofn.Flags       = OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST;
    return GetSaveFileName(&ofn);
}
