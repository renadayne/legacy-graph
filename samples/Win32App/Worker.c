#include "App.h"

typedef struct tagSAVEPARAM {
    HWND hWnd;
    DOCUMENT* pDoc;
} SAVEPARAM;

static DWORD WINAPI SaveThreadProc(LPVOID pv)
{
    SAVEPARAM* p = (SAVEPARAM*)pv;
    BOOL bOk = DocWriteFile(p->pDoc, p->pDoc->szPath);

    PostMessage(p->hWnd, WM_APP_SAVE_DONE, (WPARAM)bOk, 0);
    HeapFree(GetProcessHeap(), 0, p);
    return 0;
}

void StartBackgroundSave(HWND hWnd, DOCUMENT* pDoc)
{
    HANDLE hThread;
    SAVEPARAM* pParam = (SAVEPARAM*)HeapAlloc(GetProcessHeap(), 0, sizeof(SAVEPARAM));

    if (pParam == NULL)
        return;
    pParam->hWnd = hWnd;
    pParam->pDoc = pDoc;
    hThread = CreateThread(NULL, 0, SaveThreadProc, pParam, 0, NULL);
    if (hThread != NULL)
        CloseHandle(hThread);
}
