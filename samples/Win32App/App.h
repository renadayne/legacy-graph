#ifndef APP_H
#define APP_H

#include "Common.h"
#include "Doc.h"
#include "Options.h"

#ifdef __cplusplus
extern "C" {
#endif

extern HINSTANCE g_hInst;
extern DOCUMENT  g_doc;
extern OPTIONS   g_options;

void SetStatusText(LPCTSTR pszText);
void ShowErrorId(HWND hWnd, UINT nId);
BOOL BrowseForFile(HWND hWnd, LPTSTR pszPath, int cch);
void StartBackgroundSave(HWND hWnd, DOCUMENT* pDoc);

#ifdef __cplusplus
}
#endif

void InstallDigitFilter(HWND hEdit);
void LoadOptionsToDialog(HWND hDlg);
INT_PTR CALLBACK OptionsDlgProc(HWND hDlg, UINT msg, WPARAM wParam, LPARAM lParam);
INT_PTR CALLBACK ExportDlgProc(HWND hDlg, UINT msg, WPARAM wParam, LPARAM lParam);
INT_PTR CALLBACK AboutDlgProc(HWND hDlg, UINT msg, WPARAM wParam, LPARAM lParam);

#endif
