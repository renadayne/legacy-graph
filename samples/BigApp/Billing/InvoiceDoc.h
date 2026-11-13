// InvoiceDoc.h : interface of the CInvoiceDoc class
//
#if !defined(AFX_INVOICEDOC_H__1D2C3B4A_0010_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_)
#define AFX_INVOICEDOC_H__1D2C3B4A_0010_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif

struct INVOICELINE
{
	CString strItem;
	int     nQty;
	double  dUnitPrice;
};

class CInvoiceDoc : public CDocument
{
protected:
	CInvoiceDoc();
	DECLARE_DYNCREATE(CInvoiceDoc)

public:
	CArray<INVOICELINE, INVOICELINE&> m_lines;
	double  m_dTotal;
	double  m_dDiscount;
	int     m_nCustomerId;

	void    AddLine(const CString& strItem, int nQty, double dUnitPrice);
	void    RecalcTotal();
	double  CalcLineAmount(int nLine);
	void    ApplyDiscount(double dPercent);
	BOOL    SaveInvoice();
	double  GetLineAmount(int nLine);

	//{{AFX_VIRTUAL(CInvoiceDoc)
	public:
	virtual BOOL OnNewDocument();
	//}}AFX_VIRTUAL

	virtual ~CInvoiceDoc();

protected:
	//{{AFX_MSG(CInvoiceDoc)
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

#endif // AFX_INVOICEDOC_H__1D2C3B4A_0010_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_
