// MainFrm.cpp : implementation of the CMainFrame class
//
#include "stdafx.h"
#include "LegacyApp.h"
#include "MainFrm.h"
#include "LegacyDoc.h"
#include "ExportDlg.h"
#include "Util.h"

IMPLEMENT_DYNCREATE(CMainFrame, CFrameWnd)

BEGIN_MESSAGE_MAP(CMainFrame, CFrameWnd)
	ON_WM_CREATE()
	ON_COMMAND(ID_FILE_EXPORT, OnFileExport)
	ON_UPDATE_COMMAND_UI(ID_FILE_EXPORT, OnUpdateFileExport)
	ON_MESSAGE(WM_APP_RECALC_DONE, OnRecalcDone)
END_MESSAGE_MAP()

static UINT indicators[] =
{
	ID_SEPARATOR,           // status line indicator
	ID_INDICATOR_CAPS,
	ID_INDICATOR_NUM,
};

CMainFrame::CMainFrame()
{
}

CMainFrame::~CMainFrame()
{
}

int CMainFrame::OnCreate(LPCREATESTRUCT lpCreateStruct)
{
	if (CFrameWnd::OnCreate(lpCreateStruct) == -1)
		return -1;

	if (!m_wndToolBar.CreateEx(this) || !m_wndToolBar.LoadToolBar(IDR_MAINFRAME))
	{
		TRACE0("Failed to create toolbar\n");
		return -1;
	}
	if (!m_wndStatusBar.Create(this))
		return -1;
	m_wndStatusBar.SetIndicators(indicators, sizeof(indicators)/sizeof(UINT));
	return 0;
}

BOOL CMainFrame::PreCreateWindow(CREATESTRUCT& cs)
{
	if( !CFrameWnd::PreCreateWindow(cs) )
		return FALSE;
	return TRUE;
}

void CMainFrame::OnFileExport()
{
	CExportDlg dlg(this);
	if (dlg.DoModal() != IDOK)
		return;

	CLegacyDoc* pDoc = (CLegacyDoc*)GetActiveDocument();
	if (pDoc == NULL)
		return;

	if (!pDoc->ExportTo(dlg.m_strPath, dlg.m_nFormat, dlg.m_bOverwrite))
	{
		AfxMessageBox(_T("Export failed"));
		util::LogMessage(_T("Export failed"));
	}
}

void CMainFrame::OnUpdateFileExport(CCmdUI* pCmdUI)
{
	CLegacyDoc* pDoc = (CLegacyDoc*)GetActiveDocument();
	pCmdUI->Enable(pDoc != NULL && pDoc->HasData());
}

LRESULT CMainFrame::OnRecalcDone(WPARAM wParam, LPARAM lParam)
{
	UNREFERENCED_PARAMETER(lParam);
	CString msg;
	msg.Format(_T("Recalculated %d rows"), (int)wParam);
	m_wndStatusBar.SetPaneText(0, msg);
	Refresh();
	return 0;
}

void CMainFrame::Refresh()
{
	RedrawWindow();
}
