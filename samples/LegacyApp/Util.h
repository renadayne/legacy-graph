// Util.h : helpers shared since the VC6 days
#pragma once

namespace util
{
	void    LogMessage(const CString& msg);
	BOOL    FileExists(const CString& path);
	BOOL    IsValidPath(const CString& path);
	BOOL    WriteTextFile(const CString& path, const CString& text);
	CString FormatNumber(double value);
}

CWnd* GetRefreshTarget();
