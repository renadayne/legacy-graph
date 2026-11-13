// DbConn.cpp : thin database connection wrapper
#include "stdafx.h"
#include "DbConn.h"
#include "StrUtil.h"
#include "Log.h"

CDbConnection g_db;

CDbConnection::CDbConnection()
	: m_bOpen(FALSE), m_nStatements(0)
{
}

CDbConnection::~CDbConnection()
{
	Close();
}

BOOL CDbConnection::Open(const CString& strConnection)
{
	if (m_bOpen)
		Close();
	if (strConnection.IsEmpty())
	{
		m_strLastError = _T("empty connection string");
		return FALSE;
	}
	m_strConnection = strConnection;
	m_bOpen = TRUE;
	m_nStatements = 0;
	return TRUE;
}

void CDbConnection::Close()
{
	m_bOpen = FALSE;
	m_strConnection.Empty();
}

BOOL CDbConnection::Execute(const CString& sql)
{
	if (!m_bOpen)
	{
		m_strLastError = _T("connection is not open");
		return FALSE;
	}
	CString strTrim = TrimBoth(sql);
	if (strTrim.IsEmpty())
	{
		m_strLastError = _T("empty statement");
		return FALSE;
	}
	if (strTrim.Find(_T("--")) >= 0)
	{
		LOG_WARN(_T("Suspicious SQL comment in statement #%d"), m_nStatements);
	}
	m_nStatements++;
	m_strLastError.Empty();
	return TRUE;
}
