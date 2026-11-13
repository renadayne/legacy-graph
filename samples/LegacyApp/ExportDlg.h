// ExportDlg.h : header file
#pragma once

class CExportDlg : public CDialog
{
// Construction
public:
	CExportDlg(CWnd* pParent = NULL);   // standard constructor

// Dialog Data
	//{{AFX_DATA(CExportDlg)
	enum { IDD = IDD_EXPORT };
	CComboBox	m_cmbFormat;
	CString	m_strPath;
	BOOL	m_bOverwrite;
	int		m_nFormat;
	//}}AFX_DATA

// Overrides
	//{{AFX_VIRTUAL(CExportDlg)
protected:
	virtual void DoDataExchange(CDataExchange* pDX);    // DDX/DDV support
	virtual BOOL OnInitDialog();
	virtual void OnOK();
	//}}AFX_VIRTUAL

// Implementation
protected:
	//{{AFX_MSG(CExportDlg)
	afx_msg void OnBnClickedBrowse();
	afx_msg void OnSelchangeFormat();
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};
