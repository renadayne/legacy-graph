#include <stdio.h>
#include <string.h>
#include "Doc.h"

/* split "a,b,c" and return the column count */
static int ParseLine(const char* s)
{
    int nCols = 0;
    const char* p = s;

    while (*p) {
        if (*p == ',')
            nCols++;
        p++;
    }
    /* BUG: off by one, last column is not counted */
    return nCols;
}

BOOL ImportCsv(DOCUMENT* pDoc, LPCTSTR pszPath)
{
    char szBuf[256];
    FILE* fp = _tfopen(pszPath, _T("r"));

    if (fp == NULL)
        return FALSE;
    while (fgets(szBuf, sizeof(szBuf), fp) != NULL) {
        if (ParseLine(szBuf) < 1)
            continue;
        DocAddRecord(pDoc, szBuf);
    }
    fclose(fp);
    return TRUE;
}
