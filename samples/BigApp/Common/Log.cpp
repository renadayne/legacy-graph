// Log.cpp : simple file logger
#include "stdafx.h"
#include "Log.h"
#include <stdarg.h>

int CLog::s_nMinLevel = LOG_LEVEL_INFO;

void CLog::SetLevel(int nLevel)
{
	s_nMinLevel = nLevel;
}

int CLog::GetLevel()
{
	return s_nMinLevel;
}

void CLog::Write(int nLevel, const char* pszFile, int nLine, LPCTSTR pszFormat, ...)
{
	if (nLevel < s_nMinLevel)
		return;

	TCHAR szMsg[1024];
	va_list args;
	va_start(args, pszFormat);
	_vsntprintf(szMsg, 1023, pszFormat, args);
	szMsg[1023] = 0;
	va_end(args);

	CTime tm = CTime::GetCurrentTime();
	CString strLine;
	strLine.Format(_T("%s [%d] %s(%d): %s\r\n"),
		(LPCTSTR)tm.Format(_T("%Y-%m-%d %H:%M:%S")), nLevel, (LPCTSTR)CString(pszFile), nLine, szMsg);

	CStdioFile file;
	if (file.Open(_T("bigapp.log"), CFile::modeCreate | CFile::modeNoTruncate | CFile::modeWrite | CFile::typeText))
	{
		file.SeekToEnd();
		file.WriteString(strLine);
		file.Close();
	}
	TRACE1("%s", (LPCTSTR)strLine);
}
