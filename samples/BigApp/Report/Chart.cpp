// Chart.cpp : simple bar chart window helper
#include "stdafx.h"
#include "Chart.h"

CChartWnd::CChartWnd()
{
}

void CChartWnd::SetData(const CArray<double, double>& values, const CStringArray& labels)
{
	m_values.Copy(values);
	m_labels.Copy(labels);
}

#ifdef USE_GDIPLUS
void CChartWnd::DrawChart(CDC* pDC, const CRect& rc)
{
	// GDI+ rendering: anti-aliased bars (build with USE_GDIPLUS)
	Gdiplus::Graphics g(pDC->GetSafeHdc());
	g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
	Gdiplus::SolidBrush brush(Gdiplus::Color(255, 40, 120, 200));
	int nCount = m_values.GetSize();
	if (nCount == 0)
		return;
	int nBarW = rc.Width() / nCount;
	g.FillRectangle(&brush, rc.left, rc.top, nBarW, rc.Height() / 2);
}
#else
void CChartWnd::DrawChart(CDC* pDC, const CRect& rc)
{
	int nCount = m_values.GetSize();
	if (nCount == 0)
	{
		pDC->DrawText(_T("(no data)"), -1, (LPRECT)&rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
		return;
	}

	double dMax = 0.0;
	for (int i = 0; i < nCount; i++)
	{
		if (m_values[i] > dMax)
			dMax = m_values[i];
	}
	if (dMax <= 0.0)
		dMax = 1.0;

	CBrush brushBar(RGB(40, 120, 200));
	CPen penAxis(PS_SOLID, 1, RGB(0, 0, 0));
	CPen* pOldPen = pDC->SelectObject(&penAxis);
	pDC->MoveTo(rc.left, rc.top);
	pDC->LineTo(rc.left, rc.bottom);
	pDC->LineTo(rc.right, rc.bottom);

	int nBarW = rc.Width() / nCount;
	if (nBarW < 2)
		nBarW = 2;
	for (int j = 0; j < nCount; j++)
	{
		int nBarH = (int)(rc.Height() * m_values[j] / dMax);
		CRect rcBar(rc.left + j * nBarW + 1, rc.bottom - nBarH,
			rc.left + (j + 1) * nBarW - 1, rc.bottom);
		pDC->FillRect(&rcBar, &brushBar);
		if (j < m_labels.GetSize() && nBarW > 24)
			pDC->TextOut(rcBar.left, rc.bottom + 2, m_labels[j]);
	}
	pDC->SelectObject(pOldPen);
}
#endif
