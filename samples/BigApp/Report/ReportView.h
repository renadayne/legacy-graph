// ReportView.h : interface of the CReportView class
//
#if !defined(AFX_REPORTVIEW_H__1D2C3B4A_0021_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_)
#define AFX_REPORTVIEW_H__1D2C3B4A_0021_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif

#include "Chart.h"

class CReportDoc;

class CReportView : public CView
{
protected:
	CReportView();
	DECLARE_DYNCREATE(CReportView)

public:
	CReportDoc* GetDocument();

	//{{AFX_VIRTUAL(CReportView)
	public:
	virtual void OnDraw(CDC* pDC);
	virtual void OnInitialUpdate();
	//}}AFX_VIRTUAL

	virtual ~CReportView();

protected:
	CChartWnd m_chart;

	//{{AFX_MSG(CReportView)
	afx_msg void OnFileExportPdf();
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

#endif // AFX_REPORTVIEW_H__1D2C3B4A_0021_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_
