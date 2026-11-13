// MainFrm.h : interface of the CMainFrame class
#pragma once

class CMainFrame : public CFrameWnd
{
protected: // create from serialization only
	CMainFrame();
	DECLARE_DYNCREATE(CMainFrame)

public:
	virtual BOOL PreCreateWindow(CREATESTRUCT& cs);
	virtual ~CMainFrame();
	void Refresh();

protected:  // control bar embedded members
	CToolBar    m_wndToolBar;
	CStatusBar  m_wndStatusBar;

// Generated message map functions
protected:
	afx_msg int OnCreate(LPCREATESTRUCT lpCreateStruct);
	afx_msg void OnFileExport();
	afx_msg void OnUpdateFileExport(CCmdUI* pCmdUI);
	afx_msg LRESULT OnRecalcDone(WPARAM wParam, LPARAM lParam);
	DECLARE_MESSAGE_MAP()
};
