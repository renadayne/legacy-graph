// ReportBuilder.h : builds report data
#ifndef BIGAPP_REPORTBUILDER_H
#define BIGAPP_REPORTBUILDER_H

class CReportBuilder
{
public:
	CReportBuilder();

	BOOL    BuildMonthly(int nMonth);
	CString GetTitle() const { return m_strTitle; }

	CArray<double, double> m_values;

private:
	int     LoadRows(int nMonth);
	CString m_strTitle;
};

#endif
