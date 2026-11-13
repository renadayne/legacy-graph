// InvoiceDlg.h : header file
//
#if !defined(AFX_INVOICEDLG_H__1D2C3B4A_0011_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_)
#define AFX_INVOICEDLG_H__1D2C3B4A_0011_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif

#include "Customer.h"

class CInvoiceDoc;

class CInvoiceDlg : public CDialog
{
public:
	CInvoiceDlg(CInvoiceDoc* pDoc, CWnd* pParent = NULL);

	//{{AFX_DATA(CInvoiceDlg)
	enum { IDD = IDD_INVOICE };
	CComboBox	m_cmbCustomer;
	double		m_dDiscount;
	//}}AFX_DATA

	//{{AFX_VIRTUAL(CInvoiceDlg)
	protected:
	virtual void DoDataExchange(CDataExchange* pDX);
	//}}AFX_VIRTUAL

protected:
	CInvoiceDoc*  m_pDoc;
	CCustomerList m_customers;

	//{{AFX_MSG(CInvoiceDlg)
	virtual BOOL OnInitDialog();
	virtual void OnOK();
	afx_msg void OnBnClickedRecalc();
	afx_msg void OnBnClickedClearDiscount();
	afx_msg void OnCbnSelchangeCustomer();
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

#endif // AFX_INVOICEDLG_H__1D2C3B4A_0011_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_
