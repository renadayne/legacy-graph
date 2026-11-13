// StrUtil.h : string helpers
#ifndef BIGAPP_STRUTIL_H
#define BIGAPP_STRUTIL_H

CString TrimBoth(const CString& str);
CString QuoteSql(const CString& str);
BOOL    StartsWithNoCase(const CString& str, const CString& strPrefix);
int     SplitString(const CString& str, TCHAR chSep, CStringArray& arr);

#endif
