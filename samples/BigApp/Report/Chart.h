// Chart.h : simple bar chart window helper
#ifndef BIGAPP_CHART_H
#define BIGAPP_CHART_H

class CChartWnd
{
public:
	CChartWnd();

	void SetData(const CArray<double, double>& values, const CStringArray& labels);
	void DrawChart(CDC* pDC, const CRect& rc);

private:
	CArray<double, double> m_values;
	CStringArray           m_labels;
};

#endif
