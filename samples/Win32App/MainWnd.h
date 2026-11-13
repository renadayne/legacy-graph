#ifndef MAINWND_H
#define MAINWND_H

#include "App.h"

LRESULT CALLBACK MainWndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);
void OnSaveDone(HWND hWnd, BOOL bOk);
VOID CALLBACK BlinkTimerProc(HWND hWnd, UINT uMsg, UINT_PTR idEvent, DWORD dwTime);

#endif
