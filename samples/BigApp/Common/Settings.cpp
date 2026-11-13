// Settings.cpp : persistent application settings
#include "stdafx.h"
#include "Settings.h"
#include "Log.h"

CAppSettings g_settings;

static const TCHAR szSection[] = _T("Billing");

CAppSettings::CAppSettings()
{
	m_nVatRate = 10;
	m_nRounding = 0;
}

void CAppSettings::Load()
{
	CWinApp* pApp = AfxGetApp();
	m_nVatRate    = pApp->GetProfileInt(szSection, _T("VatRate"), 10);
	m_nRounding   = pApp->GetProfileInt(szSection, _T("Rounding"), 0);
	m_strCompany  = pApp->GetProfileString(szSection, _T("Company"), _T(""));
	m_strConnection = pApp->GetProfileString(szSection, _T("Connection"), _T("DSN=bigapp"));
	if (m_nVatRate < 0 || m_nVatRate > 100)
		m_nVatRate = 10;
}

BOOL CAppSettings::Save()
{
	CWinApp* pApp = AfxGetApp();
	if (!pApp->WriteProfileInt(szSection, _T("VatRate"), m_nVatRate))
	{
		LOG_ERROR(_T("Cannot write VatRate %d"), m_nVatRate);
		return FALSE;
	}
	pApp->WriteProfileInt(szSection, _T("Rounding"), m_nRounding);
	pApp->WriteProfileString(szSection, _T("Company"), m_strCompany);
	pApp->WriteProfileString(szSection, _T("Connection"), m_strConnection);
	return TRUE;
}
