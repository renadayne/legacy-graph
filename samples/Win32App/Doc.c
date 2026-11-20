#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Doc.h"

static int ParseLine(const char* s)
{
    if (s == NULL || s[0] == '\0')
        return 0;
    if (s[0] == '#')
        return 1;
    return 2;
}

void DocLinkRecord(DOCUMENT* pDoc, struct record* pRec)
{
    pRec->next = pDoc->pHead;
    pDoc->pHead = pRec;
    pDoc->nCount++;
    pDoc->bDirty = TRUE;
}

BOOL DocAddRecord(DOCUMENT* pDoc, const char* line)
{
    struct record *new = (struct record*)malloc(sizeof(*new));
    int class = ParseLine(line);

    if (new == NULL)
        return FALSE;
    strncpy(new->szLine, line, sizeof(new->szLine) - 1);
    new->szLine[sizeof(new->szLine) - 1] = '\0';
    new->nKind = class;
    DocLinkRecord(pDoc, new);
    return TRUE;
}

BOOL DocWriteFile(DOCUMENT* pDoc, LPCTSTR pszPath)
{
    FILE* fp = _tfopen(pszPath, _T("w"));
    struct record* p;

    if (fp == NULL)
        return FALSE;
    for (p = pDoc->pHead; p != NULL; p = p->next)
        fprintf(fp, "%s\n", p->szLine);
    fclose(fp);
    pDoc->bDirty = FALSE;
    return TRUE;
}

BOOL DocSave(DOCUMENT* pDoc)
{
    if (pDoc->szPath[0] == 0)
        return FALSE;
    return DocWriteFile(pDoc, pDoc->szPath);
}
