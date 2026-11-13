// BigApp.h : main header file for the BIGAPP application
//
#if !defined(AFX_BIGAPP_H__1D2C3B4A_0001_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_)
#define AFX_BIGAPP_H__1D2C3B4A_0001_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif

#include "resource.h"

class CBigApp : public CWinApp
{
public:
	CBigApp();

	CMultiDocTemplate* m_pInvoiceTemplate;
	CMultiDocTemplate* m_pReportTemplate;

	//{{AFX_VIRTUAL(CBigApp)
	public:
	virtual BOOL InitInstance();
	virtual int ExitInstance();
	//}}AFX_VIRTUAL

	//{{AFX_MSG(CBigApp)
	afx_msg void OnAppAbout();
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

extern CBigApp theApp;

#endif // AFX_BIGAPP_H__1D2C3B4A_0001_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_
