// LegacyView.cpp : implementation of the CLegacyView class
//
#include "stdafx.h"
#include "LegacyApp.h"
#include "LegacyDoc.h"
#include "LegacyView.h"
#include "Util.h"

IMPLEMENT_DYNCREATE(CLegacyView, CView)

BEGIN_MESSAGE_MAP(CLegacyView, CView)
	ON_WM_LBUTTONDOWN()
	ON_COMMAND_RANGE(ID_VIEW_ZOOM_100, ID_VIEW_ZOOM_200, OnViewZoom)
	ON_COMMAND(ID_FILE_PRINT, &CView::OnFilePrint)
END_MESSAGE_MAP()

CLegacyView::CLegacyView()
	: m_nZoom(100)
{
}

CLegacyView::~CLegacyView()
{
}

BOOL CLegacyView::PreCreateWindow(CREATESTRUCT& cs)
{
	return CView::PreCreateWindow(cs);
}

CLegacyDoc* CLegacyView::GetDocument() const
{
	return (CLegacyDoc*)m_pDocument;
}

void CLegacyView::OnDraw(CDC* pDC)
{
	CLegacyDoc* pDoc = GetDocument();
	if (!pDoc)
		return;
	for (int i = 0; i < pDoc->m_values.GetSize(); i++)
	{
		CString s = util::FormatNumber(pDoc->m_values[i] * m_nZoom / 100);
		pDC->TextOut(10, 10 + i * 20, s);
	}
}

void CLegacyView::OnLButtonDown(UINT nFlags, CPoint point)
{
	GetDocument()->Recalculate();
	CView::OnLButtonDown(nFlags, point);
}

void CLegacyView::OnViewZoom(UINT nID)
{
	switch (nID)
	{
	case ID_VIEW_ZOOM_100: m_nZoom = 100; break;
	case ID_VIEW_ZOOM_150: m_nZoom = 150; break;
	case ID_VIEW_ZOOM_200: m_nZoom = 200; break;
	}
	Refresh();
}

void CLegacyView::Refresh()
{
	Invalidate();
}

// Legacy helper kept for an old plug-in; the receiver type is unknown here,
// so the call below is reported as "ambiguous" (CMainFrame::Refresh or CLegacyView::Refresh).
void RefreshAny(void* p)
{
	CWnd* pWnd = (CWnd*)p;
	if (pWnd)
		((CLegacyView*)pWnd)->Invalidate();
	GetRefreshTarget()->Refresh();
}
