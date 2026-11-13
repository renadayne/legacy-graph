// InvoiceDoc.cpp : implementation of the CInvoiceDoc class
//
#include "stdafx.h"
#include "../BigApp.h"
#include "InvoiceDoc.h"
#include "TaxCalc.h"
#include "../Common/Money.h"
#include "../Common/DbConn.h"
#include "../Common/StrUtil.h"
#include "../Common/Settings.h"
#include "../Common/Log.h"

IMPLEMENT_DYNCREATE(CInvoiceDoc, CDocument)

BEGIN_MESSAGE_MAP(CInvoiceDoc, CDocument)
	//{{AFX_MSG_MAP(CInvoiceDoc)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

CInvoiceDoc::CInvoiceDoc()
{
	m_dTotal = 0.0;
	m_dDiscount = 0.0;
	m_nCustomerId = 0;
}

CInvoiceDoc::~CInvoiceDoc()
{
}

BOOL CInvoiceDoc::OnNewDocument()
{
	if (!CDocument::OnNewDocument())
		return FALSE;
	m_lines.RemoveAll();
	m_dTotal = 0.0;
	m_dDiscount = 0.0;
	AddLine(_T("Widget"), 3, 19.99);
	AddLine(_T("Gadget"), 1, 249.50);
	RecalcTotal();
	return TRUE;
}

void CInvoiceDoc::AddLine(const CString& strItem, int nQty, double dUnitPrice)
{
	INVOICELINE line;
	line.strItem = strItem;
	line.nQty = nQty;
	line.dUnitPrice = dUnitPrice;
	m_lines.Add(line);
}

double CInvoiceDoc::CalcLineAmount(int nLine)
{
	if (nLine < 0 || nLine >= m_lines.GetSize())
		return 0.0;

	const INVOICELINE& line = m_lines[nLine];
	double dNet = line.nQty * line.dUnitPrice;
	double dVat = CTaxCalculator::ComputeVat(dNet);
	return RoundMoney(dNet + dVat, 2);
}

double CInvoiceDoc::GetLineAmount(int nLine)
{
	return CalcLineAmount(nLine);
}

void CInvoiceDoc::RecalcTotal()
{
	double dSum = 0.0;
	int nCount = m_lines.GetSize();
	for (int i = 0; i < nCount; i++)
	{
		dSum += CalcLineAmount(i);
	}
	if (m_dDiscount > 0.0)
		dSum -= dSum * m_dDiscount / 100.0;
	m_dTotal = RoundMoney(dSum, 2);
	SetModifiedFlag(TRUE);
	UpdateAllViews(NULL);
}

void CInvoiceDoc::ApplyDiscount(double dPercent)
{
	if (dPercent < 0.0)
		dPercent = 0.0;
	if (dPercent > 100.0)
		dPercent = 100.0;
	m_dDiscount = dPercent;
}

BOOL CInvoiceDoc::SaveInvoice()
{
	CString sql;
	sql.Format(_T("INSERT INTO invoice (customer_id, total, discount) VALUES (%d, %s, %s)"),
		m_nCustomerId, (LPCTSTR)FormatMoney(m_dTotal), (LPCTSTR)FormatMoney(m_dDiscount));

	if (!g_db.Execute(sql))
	{
		LOG_ERROR(_T("SaveInvoice failed: %s"), (LPCTSTR)g_db.GetLastError());
		return FALSE;
	}
	for (int i = 0; i < m_lines.GetSize(); i++)
	{
		const INVOICELINE& line = m_lines[i];
		CString sqlLine;
		sqlLine.Format(_T("INSERT INTO invoice_line (item, qty) VALUES (%s, %d)"),
			(LPCTSTR)QuoteSql(line.strItem), line.nQty);
		if (!g_db.Execute(sqlLine))
		{
			LOG_ERROR(_T("SaveInvoice line %d failed"), i);
			return FALSE;
		}
	}
	SetModifiedFlag(FALSE);
	return TRUE;
}
