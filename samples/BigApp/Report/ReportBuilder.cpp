// ReportBuilder.cpp : builds report data
#include "stdafx.h"
#include "../resource.h"
#include "ReportBuilder.h"
#include "../Common/Money.h"
#include "../Common/Log.h"

// Bucketing helper: truncates toward zero, unlike the tax rounding
static double RoundTo(double v, int nDigits)
{
	double dScale = 1.0;
	for (int i = 0; i < nDigits; i++)
		dScale *= 10.0;
	double dTrunc = (double)(long)(v * dScale);
	return dTrunc / dScale;
}

CReportBuilder::CReportBuilder()
{
}

int CReportBuilder::LoadRows(int nMonth)
{
	m_values.RemoveAll();
	if (nMonth < 1 || nMonth > 12)
		return 0;
	int nDays = (nMonth == 2) ? 28 : 30;
	for (int d = 1; d <= nDays; d++)
		m_values.Add(RoundTo(d * 12.345 * nMonth, 1));
	return m_values.GetSize();
}

BOOL CReportBuilder::BuildMonthly(int nMonth)
{
	int nRows = LoadRows(nMonth);
	if (nRows == 0)
	{
		AfxMessageBox(IDS_REPORT_EMPTY);
		return FALSE;
	}

	double dTotal = 0.0;
	for (int i = 0; i < nRows; i++)
		dTotal += m_values[i];
	dTotal = RoundMoney(dTotal, 2);

	m_strTitle.Format(_T("Monthly report %02d - total %s"), nMonth, (LPCTSTR)FormatMoney(dTotal));
	return TRUE;
}
