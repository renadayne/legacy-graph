#ifndef DOC_H
#define DOC_H

#include "Common.h"

struct record {
    char szLine[256];
    int nKind;
    struct record *next;
};

typedef struct tagDOCUMENT {
    TCHAR szPath[MAX_PATH];
    struct record *pHead;
    int nCount;
    BOOL bDirty;
} DOCUMENT;

#ifdef __cplusplus
extern "C" {
#endif

BOOL DocSave(DOCUMENT* pDoc);
BOOL DocWriteFile(DOCUMENT* pDoc, LPCTSTR pszPath);
BOOL DocAddRecord(DOCUMENT* pDoc, const char* line);
void DocLinkRecord(DOCUMENT* pDoc, struct record* pRec);
BOOL ImportCsv(DOCUMENT* pDoc, LPCTSTR pszPath);
BOOL ExportCsv(DOCUMENT* pDoc, LPCTSTR pszPath);

#ifdef __cplusplus
}
#endif

#endif
