// LegacyView.h : interface of the CLegacyView class
#pragma once

class CLegacyDoc;

class CLegacyView : public CView
{
protected: // create from serialization only
	CLegacyView();
	DECLARE_DYNCREATE(CLegacyView)

public:
	CLegacyDoc* GetDocument() const;
	void Refresh();

public:
	virtual void OnDraw(CDC* pDC);
	virtual BOOL PreCreateWindow(CREATESTRUCT& cs);
	virtual ~CLegacyView();

protected:
	int m_nZoom;

protected:
	afx_msg void OnLButtonDown(UINT nFlags, CPoint point);
	afx_msg void OnViewZoom(UINT nID);
	DECLARE_MESSAGE_MAP()
};
