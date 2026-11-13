// Util.cpp
#include "stdafx.h"
#include "Util.h"

namespace util
{

void LogMessage(const CString& msg)
{
	CStdioFile f;
	if (f.Open(_T("legacy.log"), CFile::modeCreate | CFile::modeNoTruncate | CFile::modeWrite))
	{
		f.SeekToEnd();
		f.WriteString(msg + _T("\n"));
	}
	TRACE(_T("%s\n"), (LPCTSTR)msg);
}

BOOL FileExists(const CString& path)
{
	return ::GetFileAttributes(path) != INVALID_FILE_ATTRIBUTES;
}

BOOL IsValidPath(const CString& path)
{
	if (path.GetLength() > MAX_PATH)
	{
		LogMessage(_T("Path too long"));
		return FALSE;
	}
	return path.FindOneOf(_T("*?\"<>|")) < 0;
}

#ifdef _UNICODE
BOOL WriteTextFile(const CString& path, const CString& text)
{
	CStdioFile f;
	if (!f.Open(path, CFile::modeCreate | CFile::modeWrite | CFile::typeUnicode)) {
		LogMessage(_T("Cannot open ") + path);
		return FALSE;
	}
	f.WriteString(text);
	return TRUE;
}
#else
BOOL WriteTextFile(const CString& path, const CString& text)
{
	CStdioFile f;
	if (!f.Open(path, CFile::modeCreate | CFile::modeWrite)) {
		return FALSE;
	}
	f.WriteString(text);
	return TRUE;
}
#endif

CString FormatNumber(double value)
{
	CString s;
	s.Format(_T("%.2f"), value);
	return s;
}

#if 0
// Dead code from 1998, braces intentionally unbalanced: the indexer must skip it.
void OldFormat(double v) {
	if (v > 0) {
		printf("%f", v);
#endif

}  // namespace util

CWnd* GetRefreshTarget()
{
	return AfxGetMainWnd();
}
