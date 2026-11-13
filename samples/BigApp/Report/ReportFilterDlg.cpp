// ReportFilterDlg.cpp : implementation file
//
#include "stdafx.h"
#include "../BigApp.h"
#include "ReportFilterDlg.h"

CReportFilterDlg::CReportFilterDlg(CWnd* pParent /*=NULL*/)
	: CDialog(CReportFilterDlg::IDD, pParent)
{
	//{{AFX_DATA_INIT(CReportFilterDlg)
	m_nMonth = 0;
	m_nYear = 2015;
	m_bIncludeTax = TRUE;
	//}}AFX_DATA_INIT
}

void CReportFilterDlg::DoDataExchange(CDataExchange* pDX)
{
	CDialog::DoDataExchange(pDX);
	//{{AFX_DATA_MAP(CReportFilterDlg)
	DDX_Control(pDX, IDC_CMB_MONTH, m_cmbMonth);
	DDX_CBIndex(pDX, IDC_CMB_MONTH, m_nMonth);
	DDX_Text(pDX, IDC_EDIT_YEAR, m_nYear);
	DDV_MinMaxInt(pDX, m_nYear, 1990, 2100);
	DDX_Check(pDX, IDC_CHK_INCLUDE_TAX, m_bIncludeTax);
	//}}AFX_DATA_MAP
}

BEGIN_MESSAGE_MAP(CReportFilterDlg, CDialog)
	//{{AFX_MSG_MAP(CReportFilterDlg)
	ON_BN_CLICKED(IDC_BTN_APPLY_FILTER, OnBnClickedApplyFilter)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

BOOL CReportFilterDlg::OnInitDialog()
{
	CDialog::OnInitDialog();
	for (int i = 1; i <= 12; i++)
	{
		CString strMonth;
		strMonth.Format(_T("%02d"), i);
		m_cmbMonth.AddString(strMonth);
	}
	m_cmbMonth.SetCurSel(m_nMonth);
	return TRUE;
}

void CReportFilterDlg::OnBnClickedApplyFilter()
{
	if (!UpdateData(TRUE))
		return;
	// the combo is zero based, the report builder wants 1..12
	m_nMonth = m_nMonth + 1;
	EndDialog(IDOK);
}
