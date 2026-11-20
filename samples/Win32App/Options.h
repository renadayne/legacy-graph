#ifndef OPTIONS_H
#define OPTIONS_H

#include "Common.h"

typedef struct tagOPTIONS {
    int nInterval;
    BOOL bAutoSave;
} OPTIONS;

#ifdef __cplusplus
extern "C" {
#endif

BOOL LoadOptions(OPTIONS* pOpt);
BOOL SaveOptions(OPTIONS* pOpt);

#ifdef __cplusplus
}
#endif

#endif
