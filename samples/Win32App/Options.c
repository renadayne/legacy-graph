#include "Options.h"

#define REG_KEY_APP _T("Software\\Example\\Win32App")
#define INI_FILE    _T("Win32App.ini")

OPTIONS g_options;

BOOL LoadOptions(OPTIONS* pOpt)
{
#ifdef USE_INI_FILE
    pOpt->nInterval = GetPrivateProfileInt(_T("Options"), _T("Interval"), 60, INI_FILE);
    pOpt->bAutoSave = GetPrivateProfileInt(_T("Options"), _T("AutoSave"), 1, INI_FILE);
    return TRUE;
#else
    HKEY hKey;
    DWORD dwType, dwSize;
    DWORD dwValue;

    pOpt->nInterval = 60;
    pOpt->bAutoSave = TRUE;
    if (RegOpenKeyEx(HKEY_CURRENT_USER, REG_KEY_APP, 0, KEY_READ, &hKey) != ERROR_SUCCESS)
        return FALSE;
    dwSize = sizeof(dwValue);
    if (RegQueryValueEx(hKey, _T("Interval"), NULL, &dwType, (LPBYTE)&dwValue, &dwSize) == ERROR_SUCCESS)
        pOpt->nInterval = (int)dwValue;
    dwSize = sizeof(dwValue);
    if (RegQueryValueEx(hKey, _T("AutoSave"), NULL, &dwType, (LPBYTE)&dwValue, &dwSize) == ERROR_SUCCESS)
        pOpt->bAutoSave = (BOOL)dwValue;
    RegCloseKey(hKey);
    return TRUE;
#endif
}

BOOL SaveOptions(OPTIONS* pOpt)
{
#ifdef USE_INI_FILE
    TCHAR szBuf[16];

    wsprintf(szBuf, _T("%d"), pOpt->nInterval);
    WritePrivateProfileString(_T("Options"), _T("Interval"), szBuf, INI_FILE);
    return TRUE;
#else
    HKEY hKey;
    DWORD dwDisp;
    DWORD dwValue;

    if (RegCreateKeyEx(HKEY_CURRENT_USER, REG_KEY_APP, 0, NULL, 0, KEY_WRITE,
            NULL, &hKey, &dwDisp) != ERROR_SUCCESS)
        return FALSE;
    dwValue = (DWORD)pOpt->nInterval;
    RegSetValueEx(hKey, _T("Interval"), 0, REG_DWORD, (const BYTE*)&dwValue, sizeof(dwValue));
    dwValue = (DWORD)pOpt->bAutoSave;
    RegSetValueEx(hKey, _T("AutoSave"), 0, REG_DWORD, (const BYTE*)&dwValue, sizeof(dwValue));
    RegCloseKey(hKey);
    return TRUE;
#endif
}
