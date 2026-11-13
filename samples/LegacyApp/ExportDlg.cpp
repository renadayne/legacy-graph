// ExportDlg.cpp : implementation file
// Hôòp thoaòi xuâìt dýÞ liêòu. File này ðýõòc lýu õÒ maÞ CP1258 (Windows Vietnamese) nhý code cuÞ.
//
#include "stdafx.h"
#include "LegacyApp.h"
#include "ExportDlg.h"
#include "Util.h"

CExportDlg::CExportDlg(CWnd* pParent /*=NULL*/)
	: CDialog(CExportDlg::IDD, pParent)
{
	//{{AFX_DATA_INIT(CExportDlg)
	m_strPath = _T("");
	m_bOverwrite = FALSE;
	m_nFormat = 0;
	//}}AFX_DATA_INIT
}

void CExportDlg::DoDataExchange(CDataExchange* pDX)
{
	CDialog::DoDataExchange(pDX);
	//{{AFX_DATA_MAP(CExportDlg)
	DDX_Control(pDX, IDC_CMB_FORMAT, m_cmbFormat);
	DDX_Text(pDX, IDC_EDIT_PATH, m_strPath);
	DDV_MaxChars(pDX, m_strPath, 260);
	DDX_Check(pDX, IDC_CHK_OVERWRITE, m_bOverwrite);
	DDX_CBIndex(pDX, IDC_CMB_FORMAT, m_nFormat);
	//}}AFX_DATA_MAP
}

BEGIN_MESSAGE_MAP(CExportDlg, CDialog)
	//{{AFX_MSG_MAP(CExportDlg)
	ON_BN_CLICKED(IDC_BTN_BROWSE, OnBnClickedBrowse)
	ON_CBN_SELCHANGE(IDC_CMB_FORMAT, OnSelchangeFormat)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

BOOL CExportDlg::OnInitDialog()
{
	CDialog::OnInitDialog();
	m_cmbFormat.AddString(_T("CSV"));
	m_cmbFormat.AddString(_T("XML"));
	m_cmbFormat.SetCurSel(m_nFormat);
	return TRUE;  // traÒ vêÌ TRUE trýÌ khi ðãòt focus vào control
}

void CExportDlg::OnBnClickedBrowse()
{
	CFileDialog fd(FALSE, _T("csv"), m_strPath, OFN_OVERWRITEPROMPT, _T("CSV (*.csv)|*.csv||"), this);
	if (fd.DoModal() == IDOK)
	{
		m_strPath = fd.GetPathName();
		UpdateData(FALSE);
	}
}

void CExportDlg::OnSelchangeFormat()
{
	UpdateData(TRUE);
}

void CExportDlg::OnOK()
{
	UpdateData(TRUE);
	if (m_strPath.IsEmpty())
	{
		AfxMessageBox(_T("Chýa nhâòp ðýõÌng dâÞn"));   // thông báo lôÞi
		return;
	}
	if (!util::IsValidPath(m_strPath))
		return;
	CDialog::OnOK();
}
