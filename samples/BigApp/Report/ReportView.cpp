// ReportView.cpp : implementation of the CReportView class
//
#include "stdafx.h"
#include "../BigApp.h"
#include "ReportDoc.h"
#include "ReportView.h"
#include "ExportPdf.h"

IMPLEMENT_DYNCREATE(CReportView, CView)

BEGIN_MESSAGE_MAP(CReportView, CView)
	//{{AFX_MSG_MAP(CReportView)
	ON_COMMAND(ID_FILE_PRINT_DIRECT, OnFileExportPdf)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

CReportView::CReportView()
{
}

CReportView::~CReportView()
{
}

CReportDoc* CReportView::GetDocument()
{
	ASSERT(m_pDocument->IsKindOf(RUNTIME_CLASS(CReportDoc)));
	return (CReportDoc*)m_pDocument;
}

void CReportView::OnInitialUpdate()
{
	CView::OnInitialUpdate();
	CReportDoc* pDoc = GetDocument();
	m_chart.SetData(pDoc->m_values, pDoc->m_labels);
}

void CReportView::OnDraw(CDC* pDC)
{
	CReportDoc* pDoc = GetDocument();
	ASSERT_VALID(pDoc);

	CRect rc;
	GetClientRect(&rc);
	rc.DeflateRect(10, 10);
	m_chart.SetData(pDoc->m_values, pDoc->m_labels);
	m_chart.DrawChart(pDC, rc);
}

void CReportView::OnFileExportPdf()
{
	CFileDialog fd(FALSE, _T("pdf"), NULL, OFN_OVERWRITEPROMPT, _T("PDF (*.pdf)|*.pdf||"), this);
	if (fd.DoModal() != IDOK)
		return;
	CReportExporter exporter;
	exporter.SetDocument(GetDocument());
	exporter.ExportPdf(fd.GetPathName());
}
