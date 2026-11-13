// ReportDoc.cpp : implementation of the CReportDoc class
//
#include "stdafx.h"
#include "../BigApp.h"
#include "ReportDoc.h"
#include "ReportBuilder.h"

IMPLEMENT_DYNCREATE(CReportDoc, CDocument)

BEGIN_MESSAGE_MAP(CReportDoc, CDocument)
	//{{AFX_MSG_MAP(CReportDoc)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

CReportDoc::CReportDoc()
{
	m_nMonth = 1;
}

CReportDoc::~CReportDoc()
{
}

BOOL CReportDoc::OnNewDocument()
{
	if (!CDocument::OnNewDocument())
		return FALSE;
	m_values.RemoveAll();
	m_labels.RemoveAll();
	CReportBuilder builder;
	if (builder.BuildMonthly(m_nMonth))
		SetData(m_nMonth, builder.m_values);
	return TRUE;
}

void CReportDoc::SetData(int nMonth, const CArray<double, double>& values)
{
	m_nMonth = nMonth;
	m_values.RemoveAll();
	m_labels.RemoveAll();
	for (int i = 0; i < values.GetSize(); i++)
	{
		CString strLabel;
		strLabel.Format(_T("D%d"), i + 1);
		m_values.Add(values[i]);
		m_labels.Add(strLabel);
	}
	UpdateAllViews(NULL);
}

double CReportDoc::GetMaxValue() const
{
	double dMax = 0.0;
	for (int i = 0; i < m_values.GetSize(); i++)
	{
		if (m_values[i] > dMax)
			dMax = m_values[i];
	}
	return dMax;
}
