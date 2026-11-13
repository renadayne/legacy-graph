// ReportDoc.h : interface of the CReportDoc class
//
#if !defined(AFX_REPORTDOC_H__1D2C3B4A_0020_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_)
#define AFX_REPORTDOC_H__1D2C3B4A_0020_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif

class CReportDoc : public CDocument
{
protected:
	CReportDoc();
	DECLARE_DYNCREATE(CReportDoc)

public:
	CArray<double, double> m_values;
	CStringArray           m_labels;
	int                    m_nMonth;

	void   SetData(int nMonth, const CArray<double, double>& values);
	double GetMaxValue() const;
	int    GetCount() const { return m_values.GetSize(); }

	//{{AFX_VIRTUAL(CReportDoc)
	public:
	virtual BOOL OnNewDocument();
	//}}AFX_VIRTUAL

	virtual ~CReportDoc();

protected:
	//{{AFX_MSG(CReportDoc)
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

#endif // AFX_REPORTDOC_H__1D2C3B4A_0020_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_
