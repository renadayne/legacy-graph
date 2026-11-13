// LegacyApp.cpp : Defines the class behaviors for the application.
//
#include "stdafx.h"
#include "LegacyApp.h"
#include "MainFrm.h"
#include "LegacyDoc.h"
#include "LegacyView.h"
#include "Util.h"

#ifdef _DEBUG
#define new DEBUG_NEW
#endif

// CLegacyApp

BEGIN_MESSAGE_MAP(CLegacyApp, CWinApp)
	ON_COMMAND(ID_APP_ABOUT, &CLegacyApp::OnAppAbout)
	// Standard file based document commands
	ON_COMMAND(ID_FILE_NEW, &CWinApp::OnFileNew)
	ON_COMMAND(ID_FILE_OPEN, &CWinApp::OnFileOpen)
END_MESSAGE_MAP()


CLegacyApp::CLegacyApp()
	: m_nRunCount(0)
{
}

CLegacyApp theApp;

BOOL CLegacyApp::InitInstance()
{
	CWinApp::InitInstance();

	SetRegistryKey(_T("Local AppWizard-Generated Applications"));
	LoadStdProfileSettings(4);
	m_nRunCount = GetProfileInt(_T("Settings"), _T("RunCount"), 0) + 1;
	util::LogMessage(_T("Application started"));

	CSingleDocTemplate* pDocTemplate;
	pDocTemplate = new CSingleDocTemplate(
		IDR_MAINFRAME,
		RUNTIME_CLASS(CLegacyDoc),
		RUNTIME_CLASS(CMainFrame),       // main SDI frame window
		RUNTIME_CLASS(CLegacyView));
	if (!pDocTemplate)
		return FALSE;
	AddDocTemplate(pDocTemplate);

	CCommandLineInfo cmdInfo;
	ParseCommandLine(cmdInfo);
	if (!ProcessShellCommand(cmdInfo))
		return FALSE;

	m_pMainWnd->ShowWindow(SW_SHOW);
	m_pMainWnd->UpdateWindow();
	return TRUE;
}

int CLegacyApp::ExitInstance()
{
	WriteProfileInt(_T("Settings"), _T("RunCount"), m_nRunCount);
	return CWinApp::ExitInstance();
}


// CAboutDlg dialog used for App About (classic AppWizard layout: class lives in the .cpp)

class CAboutDlg : public CDialog
{
public:
	CAboutDlg();

	enum { IDD = IDD_ABOUTBOX };

protected:
	virtual void DoDataExchange(CDataExchange* pDX);    // DDX/DDV support

	DECLARE_MESSAGE_MAP()
};

CAboutDlg::CAboutDlg() : CDialog(CAboutDlg::IDD)
{
}

void CAboutDlg::DoDataExchange(CDataExchange* pDX)
{
	CDialog::DoDataExchange(pDX);
}

BEGIN_MESSAGE_MAP(CAboutDlg, CDialog)
END_MESSAGE_MAP()

// App command to run the dialog
void CLegacyApp::OnAppAbout()
{
	CAboutDlg aboutDlg;
	aboutDlg.DoModal();
}
