#include <stdio.h>
#include "Doc.h"

BOOL ExportCsv(DOCUMENT* pDoc, LPCTSTR pszPath)
{
    FILE* fp = _tfopen(pszPath, _T("w"));
    struct record* p;

    if (fp == NULL)
        return FALSE;
    for (p = pDoc->pHead; p != NULL; p = p->next)
        fprintf(fp, "%d,%s\n", p->nKind, p->szLine);
    fclose(fp);
    return TRUE;
}
