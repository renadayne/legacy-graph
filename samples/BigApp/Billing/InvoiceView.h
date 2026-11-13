// InvoiceView.h : interface of the CInvoiceView class
//
#if !defined(AFX_INVOICEVIEW_H__1D2C3B4A_0012_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_)
#define AFX_INVOICEVIEW_H__1D2C3B4A_0012_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif

#include "PaymentWorker.h"

class CInvoiceDoc;

class CInvoiceView : public CFormView
{
protected:
	CInvoiceView();
	DECLARE_DYNCREATE(CInvoiceView)

public:
	//{{AFX_DATA(CInvoiceView)
	enum { IDD = IDD_INVOICE };
	CListCtrl	m_listLines;
	CString		m_strAmount;
	//}}AFX_DATA

	CInvoiceDoc* GetDocument();

	//{{AFX_VIRTUAL(CInvoiceView)
	public:
	virtual void OnInitialUpdate();
	virtual void OnUpdate(CView* pSender, LPARAM lHint, CObject* pHint);
	protected:
	virtual void DoDataExchange(CDataExchange* pDX);
	//}}AFX_VIRTUAL

	virtual ~CInvoiceView();

protected:
	CPaymentWorker m_payment;

	void FillList();
	void UpdateAmountLabel();

	//{{AFX_MSG(CInvoiceView)
	afx_msg void OnInvoiceRecalc();
	afx_msg void OnInvoicePay();
	afx_msg void OnItemChangedLines(NMHDR* pNMHDR, LRESULT* pResult);
	afx_msg LRESULT OnPaymentDone(WPARAM wParam, LPARAM lParam);
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

#endif // AFX_INVOICEVIEW_H__1D2C3B4A_0012_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_
