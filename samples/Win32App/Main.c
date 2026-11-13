#include "App.h"

HINSTANCE g_hInst;
DOCUMENT  g_doc;
OPTIONS   g_options;

LRESULT CALLBACK MainWndProc(HWND, UINT, WPARAM, LPARAM);

static BOOL RegisterMainClass(HINSTANCE hInstance)
{
    WNDCLASS wc;

    ZeroMemory(&wc, sizeof(wc));
    wc.style         = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc   = MainWndProc;
    wc.hInstance     = hInstance;
    wc.hCursor       = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszMenuName  = MAKEINTRESOURCE(IDR_MAINMENU);
    wc.lpszClassName = _T("Win32AppMain");
    return RegisterClass(&wc) != 0;
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrev, LPSTR lpCmdLine, int nCmdShow)
{
    MSG msg;
    HWND hWnd;
    HACCEL hAccel;

    g_hInst = hInstance;
    LoadOptions(&g_options);
    if (!RegisterMainClass(hInstance))
        return 1;

    hWnd = CreateWindow(_T("Win32AppMain"), _T("Win32App"), WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, 640, 480, NULL, NULL, hInstance, NULL);
    if (hWnd == NULL)
        return 2;
    ShowWindow(hWnd, nCmdShow);
    UpdateWindow(hWnd);
    hAccel = LoadAccelerators(hInstance, MAKEINTRESOURCE(IDR_ACCEL));

    while (GetMessage(&msg, NULL, 0, 0)) {
        if (!TranslateAccelerator(hWnd, hAccel, &msg)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
    }
    return (int)msg.wParam;
}
