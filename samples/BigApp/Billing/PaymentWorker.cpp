// PaymentWorker.cpp : background payment processing
#include "stdafx.h"
#include "PaymentWorker.h"
#include "../Common/DbConn.h"
#include "../Common/Log.h"

static UINT PaymentThreadProc(LPVOID pParam)
{
	CPaymentWorker* pWorker = (CPaymentWorker*)pParam;
	int nCount = pWorker->ProcessPayments();
	if (pWorker->m_pNotify != NULL && ::IsWindow(pWorker->m_pNotify->GetSafeHwnd()))
		pWorker->m_pNotify->PostMessage(WM_APP_PAYMENT_DONE, nCount, 0);
	pWorker->m_pThread = NULL;
	return 0;
}

CPaymentWorker::CPaymentWorker()
	: m_pNotify(NULL), m_pThread(NULL), m_nProcessed(0)
{
}

BOOL CPaymentWorker::Start(CWnd* pNotify)
{
	if (m_pThread != NULL)
	{
		LOG_WARN(_T("Payment worker already running (%d processed)"), m_nProcessed);
		return FALSE;
	}
	m_pNotify = pNotify;
	m_nProcessed = 0;
	m_pThread = AfxBeginThread(PaymentThreadProc, this);
	return m_pThread != NULL;
}

int CPaymentWorker::ProcessPayments()
{
	int nCount = 0;
	for (int i = 0; i < 5; i++)
	{
		CString sql;
		sql.Format(_T("UPDATE payment SET state = 1 WHERE id = %d"), i + 1);
		if (g_db.Execute(sql))
			nCount++;
		else
			LOG_ERROR(_T("Payment %d failed: %s"), i + 1, (LPCTSTR)g_db.GetLastError());
	}
	m_nProcessed = nCount;
	return nCount;
}
