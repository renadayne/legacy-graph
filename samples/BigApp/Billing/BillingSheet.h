// BillingSheet.h : billing options property sheet
#ifndef BIGAPP_BILLINGSHEET_H
#define BIGAPP_BILLINGSHEET_H

class CGeneralPage : public CPropertyPage
{
	DECLARE_DYNCREATE(CGeneralPage)
public:
	CGeneralPage();

	//{{AFX_DATA(CGeneralPage)
	enum { IDD = IDD_PAGE_GENERAL };
	CString m_strCompany;
	//}}AFX_DATA

	//{{AFX_VIRTUAL(CGeneralPage)
	public:
	virtual BOOL OnApply();
	protected:
	virtual void DoDataExchange(CDataExchange* pDX);
	//}}AFX_VIRTUAL
protected:
	//{{AFX_MSG(CGeneralPage)
	virtual BOOL OnInitDialog();
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

class CTaxPage : public CPropertyPage
{
	DECLARE_DYNCREATE(CTaxPage)
public:
	CTaxPage();

	//{{AFX_DATA(CTaxPage)
	enum { IDD = IDD_PAGE_TAX };
	int  m_nVat;
	BOOL m_bRoundUp;
	//}}AFX_DATA

	//{{AFX_VIRTUAL(CTaxPage)
	public:
	virtual BOOL OnApply();
	protected:
	virtual void DoDataExchange(CDataExchange* pDX);
	//}}AFX_VIRTUAL
protected:
	//{{AFX_MSG(CTaxPage)
	virtual BOOL OnInitDialog();
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

class CBillingOptionsSheet : public CPropertySheet
{
	DECLARE_DYNAMIC(CBillingOptionsSheet)
public:
	CBillingOptionsSheet(UINT nIDCaption, CWnd* pParentWnd = NULL);

	CGeneralPage m_pageGeneral;
	CTaxPage     m_pageTax;
};

#endif
