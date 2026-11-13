// BigApp.cpp : Defines the class behaviors for the application.
//
#include "stdafx.h"
#include "BigApp.h"
#include "MainFrm.h"
#include "ChildFrm.h"
#include "Billing/InvoiceDoc.h"
#include "Billing/InvoiceView.h"
#include "Report/ReportDoc.h"
#include "Report/ReportView.h"
#include "Common/Settings.h"
#include "Common/DbConn.h"
#include "Common/Log.h"

BEGIN_MESSAGE_MAP(CBigApp, CWinApp)
	//{{AFX_MSG_MAP(CBigApp)
	ON_COMMAND(ID_APP_ABOUT, OnAppAbout)
	//}}AFX_MSG_MAP
	ON_COMMAND(ID_FILE_NEW, CWinApp::OnFileNew)
	ON_COMMAND(ID_FILE_OPEN, CWinApp::OnFileOpen)
END_MESSAGE_MAP()

CBigApp::CBigApp()
{
	m_pInvoiceTemplate = NULL;
	m_pReportTemplate = NULL;
}

CBigApp theApp;

BOOL CBigApp::InitInstance()
{
	AfxEnableControlContainer();
	SetRegistryKey(_T("Synthetic Software"));
	LoadStdProfileSettings(8);

	g_settings.Load();
	if (!g_db.Open(g_settings.m_strConnection))
	{
		LOG_ERROR(_T("Cannot open database %s"), (LPCTSTR)g_settings.m_strConnection);
		AfxMessageBox(IDS_DB_OPEN_FAILED);
	}

	m_pInvoiceTemplate = new CMultiDocTemplate(
		IDR_INVOICETYPE,
		RUNTIME_CLASS(CInvoiceDoc),
		RUNTIME_CLASS(CChildFrame),
		RUNTIME_CLASS(CInvoiceView));
	AddDocTemplate(m_pInvoiceTemplate);

	m_pReportTemplate = new CMultiDocTemplate(
		IDR_REPORTTYPE,
		RUNTIME_CLASS(CReportDoc),
		RUNTIME_CLASS(CChildFrame),
		RUNTIME_CLASS(CReportView));
	AddDocTemplate(m_pReportTemplate);

	CMainFrame* pMainFrame = new CMainFrame;
	if (!pMainFrame->LoadFrame(IDR_MAINFRAME))
		return FALSE;
	m_pMainWnd = pMainFrame;

	CCommandLineInfo cmdInfo;
	ParseCommandLine(cmdInfo);
	if (!ProcessShellCommand(cmdInfo))
		return FALSE;

	pMainFrame->ShowWindow(m_nCmdShow);
	pMainFrame->UpdateWindow();
	return TRUE;
}

int CBigApp::ExitInstance()
{
	g_settings.Save();
	g_db.Close();
	return CWinApp::ExitInstance();
}

void CBigApp::OnAppAbout()
{
	CDialog dlgAbout(IDD_ABOUTBOX);
	dlgAbout.DoModal();
}
