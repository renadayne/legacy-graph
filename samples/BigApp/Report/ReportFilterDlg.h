// ReportFilterDlg.h : header file
//
#if !defined(AFX_REPORTFILTERDLG_H__1D2C3B4A_0022_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_)
#define AFX_REPORTFILTERDLG_H__1D2C3B4A_0022_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif

class CReportFilterDlg : public CDialog
{
public:
	CReportFilterDlg(CWnd* pParent = NULL);

	//{{AFX_DATA(CReportFilterDlg)
	enum { IDD = IDD_REPORT_FILTER };
	CComboBox	m_cmbMonth;
	int			m_nMonth;
	int			m_nYear;
	BOOL		m_bIncludeTax;
	//}}AFX_DATA

	//{{AFX_VIRTUAL(CReportFilterDlg)
	protected:
	virtual void DoDataExchange(CDataExchange* pDX);
	//}}AFX_VIRTUAL

protected:
	//{{AFX_MSG(CReportFilterDlg)
	virtual BOOL OnInitDialog();
	afx_msg void OnBnClickedApplyFilter();
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

#endif // AFX_REPORTFILTERDLG_H__1D2C3B4A_0022_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_
