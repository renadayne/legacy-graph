// PaymentWorker.h : background payment processing
#ifndef BIGAPP_PAYMENTWORKER_H
#define BIGAPP_PAYMENTWORKER_H

class CPaymentWorker
{
public:
	CPaymentWorker();

	BOOL Start(CWnd* pNotify);
	int  ProcessPayments();
	BOOL IsRunning() const { return m_pThread != NULL; }

	CWnd*       m_pNotify;
	CWinThread* m_pThread;
	int         m_nProcessed;
};

#endif
