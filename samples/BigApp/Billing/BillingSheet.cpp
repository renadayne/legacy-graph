// BillingSheet.cpp : billing options property sheet
#include "stdafx.h"
#include "../BigApp.h"
#include "BillingSheet.h"
#include "../Common/Settings.h"
#include "../Common/Log.h"

IMPLEMENT_DYNAMIC(CBillingOptionsSheet, CPropertySheet)
IMPLEMENT_DYNCREATE(CGeneralPage, CPropertyPage)
IMPLEMENT_DYNCREATE(CTaxPage, CPropertyPage)

CBillingOptionsSheet::CBillingOptionsSheet(UINT nIDCaption, CWnd* pParentWnd)
	: CPropertySheet(nIDCaption, pParentWnd)
{
	AddPage(&m_pageGeneral);
	AddPage(&m_pageTax);
}

BEGIN_MESSAGE_MAP(CGeneralPage, CPropertyPage)
	//{{AFX_MSG_MAP(CGeneralPage)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

CGeneralPage::CGeneralPage()
	: CPropertyPage(CGeneralPage::IDD)
{
	//{{AFX_DATA_INIT(CGeneralPage)
	m_strCompany = _T("");
	//}}AFX_DATA_INIT
}

void CGeneralPage::DoDataExchange(CDataExchange* pDX)
{
	CPropertyPage::DoDataExchange(pDX);
	//{{AFX_DATA_MAP(CGeneralPage)
	DDX_Text(pDX, IDC_EDIT_COMPANY, m_strCompany);
	DDV_MaxChars(pDX, m_strCompany, 64);
	//}}AFX_DATA_MAP
}

BOOL CGeneralPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();
	m_strCompany = g_settings.m_strCompany;
	UpdateData(FALSE);
	return TRUE;
}

BOOL CGeneralPage::OnApply()
{
	if (!UpdateData(TRUE))
		return FALSE;
	g_settings.m_strCompany = m_strCompany;
	return CPropertyPage::OnApply();
}

BEGIN_MESSAGE_MAP(CTaxPage, CPropertyPage)
	//{{AFX_MSG_MAP(CTaxPage)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

CTaxPage::CTaxPage()
	: CPropertyPage(CTaxPage::IDD)
{
	//{{AFX_DATA_INIT(CTaxPage)
	m_nVat = 10;
	m_bRoundUp = FALSE;
	//}}AFX_DATA_INIT
}

void CTaxPage::DoDataExchange(CDataExchange* pDX)
{
	CPropertyPage::DoDataExchange(pDX);
	//{{AFX_DATA_MAP(CTaxPage)
	DDX_Text(pDX, IDC_EDIT_VAT, m_nVat);
	DDV_MinMaxInt(pDX, m_nVat, 0, 100);
	DDX_Check(pDX, IDC_CHK_ROUND_UP, m_bRoundUp);
	//}}AFX_DATA_MAP
}

BOOL CTaxPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();
	m_nVat = g_settings.m_nVatRate;
	m_bRoundUp = (g_settings.m_nRounding == 1);
	UpdateData(FALSE);
	return TRUE;
}

BOOL CTaxPage::OnApply()
{
	if (!UpdateData(TRUE))
		return FALSE;
	g_settings.m_nVatRate = m_nVat;
	g_settings.m_nRounding = m_bRoundUp ? 1 : 0;
	if (!g_settings.Save())
	{
		LOG_ERROR(_T("Cannot persist VAT rate %d"), m_nVat);
		return FALSE;
	}
	return CPropertyPage::OnApply();
}
