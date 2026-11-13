// MainFrm.cpp : implementation of the CMainFrame class
//
#include "stdafx.h"
#include "BigApp.h"
#include "MainFrm.h"
#include "Billing/BillingSheet.h"
#include "Report/ReportBuilder.h"
#include "Report/ReportFilterDlg.h"
#include "Common/Log.h"

IMPLEMENT_DYNAMIC(CMainFrame, CMDIFrameWnd)

BEGIN_MESSAGE_MAP(CMainFrame, CMDIFrameWnd)
	//{{AFX_MSG_MAP(CMainFrame)
	ON_WM_CREATE()
	ON_COMMAND(ID_BILLING_OPTIONS, OnBillingOptions)
	ON_COMMAND(ID_REPORT_MONTHLY, OnReportMonthly)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

static UINT indicators[] =
{
	ID_SEPARATOR,
	ID_INDICATOR_CAPS,
	ID_INDICATOR_NUM,
};

CMainFrame::CMainFrame()
{
}

int CMainFrame::OnCreate(LPCREATESTRUCT lpCreateStruct)
{
	if (CMDIFrameWnd::OnCreate(lpCreateStruct) == -1)
		return -1;

	if (!m_wndToolBar.CreateEx(this, TBSTYLE_FLAT, WS_CHILD | WS_VISIBLE | CBRS_TOP) ||
		!m_wndToolBar.LoadToolBar(IDR_MAINFRAME))
	{
		TRACE0("Failed to create toolbar\n");
		return -1;
	}
	if (!m_wndStatusBar.Create(this) ||
		!m_wndStatusBar.SetIndicators(indicators, sizeof(indicators) / sizeof(UINT)))
	{
		TRACE0("Failed to create status bar\n");
		return -1;
	}
	return 0;
}

BOOL CMainFrame::PreCreateWindow(CREATESTRUCT& cs)
{
	if (!CMDIFrameWnd::PreCreateWindow(cs))
		return FALSE;
	cs.style |= WS_CLIPCHILDREN;
	return TRUE;
}

void CMainFrame::OnBillingOptions()
{
	CBillingOptionsSheet sheet(IDS_APP_TITLE, this);
	if (sheet.DoModal() == IDOK)
	{
		m_wndStatusBar.SetPaneText(0, _T("Billing options updated"));
	}
}

void CMainFrame::OnReportMonthly()
{
	CReportFilterDlg dlg(this);
	if (dlg.DoModal() != IDOK)
		return;

	CReportBuilder builder;
	if (!builder.BuildMonthly(dlg.m_nMonth))
	{
		LOG_ERROR(_T("Monthly report for month %d failed"), dlg.m_nMonth);
		return;
	}
	CBigApp* pApp = (CBigApp*)AfxGetApp();
	CDocument* pDoc = pApp->m_pReportTemplate->OpenDocumentFile(NULL);
	if (pDoc != NULL)
		pDoc->SetTitle(builder.GetTitle());
}
