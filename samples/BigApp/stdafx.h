// stdafx.h : include file for standard system include files
//
#if !defined(AFX_STDAFX_H__B16A0C21_5E7D_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_)
#define AFX_STDAFX_H__B16A0C21_5E7D_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif

#define VC_EXTRALEAN
#include <afxwin.h>
#include <afxext.h>
#include <afxdisp.h>
#include <afxcmn.h>
#include <afxdlgs.h>
#include <afxtempl.h>
#include <afxmt.h>

// Posted by the payment worker thread when a batch is finished
#define WM_APP_PAYMENT_DONE   (WM_APP + 10)

#endif // AFX_STDAFX_H__B16A0C21_5E7D_4A11_9C3E_0A1B2C3D4E5F__INCLUDED_
