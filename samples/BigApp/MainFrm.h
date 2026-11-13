// MainFrm.h : interface of the CMainFrame class
//
#if !defined(AFX_MAINFRM_H__1D2C3B4A_0002_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_)
#define AFX_MAINFRM_H__1D2C3B4A_0002_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif

class CMainFrame : public CMDIFrameWnd
{
	DECLARE_DYNAMIC(CMainFrame)
public:
	CMainFrame();

	//{{AFX_VIRTUAL(CMainFrame)
	virtual BOOL PreCreateWindow(CREATESTRUCT& cs);
	//}}AFX_VIRTUAL

protected:
	CStatusBar  m_wndStatusBar;
	CToolBar    m_wndToolBar;

	//{{AFX_MSG(CMainFrame)
	afx_msg int OnCreate(LPCREATESTRUCT lpCreateStruct);
	afx_msg void OnBillingOptions();
	afx_msg void OnReportMonthly();
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

#endif // AFX_MAINFRM_H__1D2C3B4A_0002_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_
