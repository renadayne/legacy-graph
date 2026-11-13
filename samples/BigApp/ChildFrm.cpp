// ChildFrm.cpp : implementation of the CChildFrame class
//
#include "stdafx.h"
#include "BigApp.h"
#include "ChildFrm.h"

IMPLEMENT_DYNCREATE(CChildFrame, CMDIChildWnd)

BEGIN_MESSAGE_MAP(CChildFrame, CMDIChildWnd)
	//{{AFX_MSG_MAP(CChildFrame)
	ON_WM_SIZE()
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

CChildFrame::CChildFrame()
{
}

BOOL CChildFrame::PreCreateWindow(CREATESTRUCT& cs)
{
	if (!CMDIChildWnd::PreCreateWindow(cs))
		return FALSE;
	cs.style &= ~FWS_ADDTOTITLE;
	cs.style |= WS_CLIPSIBLINGS;
	return TRUE;
}

void CChildFrame::OnSize(UINT nType, int cx, int cy)
{
	CMDIChildWnd::OnSize(nType, cx, cy);
	if (nType == SIZE_MINIMIZED)
		return;
	CWnd* pView = GetActiveView();
	if (pView != NULL && ::IsWindow(pView->GetSafeHwnd()))
		pView->Invalidate(FALSE);
}
