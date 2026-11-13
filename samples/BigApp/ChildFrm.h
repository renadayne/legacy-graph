// ChildFrm.h : interface of the CChildFrame class
//
#if !defined(AFX_CHILDFRM_H__1D2C3B4A_0003_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_)
#define AFX_CHILDFRM_H__1D2C3B4A_0003_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif

class CChildFrame : public CMDIChildWnd
{
	DECLARE_DYNCREATE(CChildFrame)
public:
	CChildFrame();

	//{{AFX_VIRTUAL(CChildFrame)
	virtual BOOL PreCreateWindow(CREATESTRUCT& cs);
	//}}AFX_VIRTUAL

protected:
	//{{AFX_MSG(CChildFrame)
	afx_msg void OnSize(UINT nType, int cx, int cy);
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

#endif // AFX_CHILDFRM_H__1D2C3B4A_0003_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_
