// StrUtil.cpp : string helpers
#include "stdafx.h"
#include "StrUtil.h"

CString TrimBoth(const CString& str)
{
	CString strOut = str;
	strOut.TrimLeft();
	strOut.TrimRight();
	return strOut;
}

CString QuoteSql(const CString& str)
{
	CString strOut = str;
	strOut.Replace(_T("'"), _T("''"));
	return _T("'") + strOut + _T("'");
}

BOOL StartsWithNoCase(const CString& str, const CString& strPrefix)
{
	if (str.GetLength() < strPrefix.GetLength())
		return FALSE;
	return str.Left(strPrefix.GetLength()).CompareNoCase(strPrefix) == 0;
}

int SplitString(const CString& str, TCHAR chSep, CStringArray& arr)
{
	arr.RemoveAll();
	int nStart = 0;
	int nPos = 0;
	while ((nPos = str.Find(chSep, nStart)) >= 0)
	{
		arr.Add(str.Mid(nStart, nPos - nStart));
		nStart = nPos + 1;
	}
	arr.Add(str.Mid(nStart));
	return arr.GetSize();
}
