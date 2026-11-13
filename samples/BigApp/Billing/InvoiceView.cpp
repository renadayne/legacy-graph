// InvoiceView.cpp : implementation of the CInvoiceView class
//
#include "stdafx.h"
#include "../BigApp.h"
#include "InvoiceDoc.h"
#include "InvoiceView.h"
#include "../Common/Money.h"
#include "../Common/Log.h"

IMPLEMENT_DYNCREATE(CInvoiceView, CFormView)

BEGIN_MESSAGE_MAP(CInvoiceView, CFormView)
	//{{AFX_MSG_MAP(CInvoiceView)
	ON_COMMAND(ID_INVOICE_RECALC, OnInvoiceRecalc)
	ON_COMMAND(ID_INVOICE_PAY, OnInvoicePay)
	ON_NOTIFY(LVN_ITEMCHANGED, IDC_LIST_LINES, OnItemChangedLines)
	ON_MESSAGE(WM_APP_PAYMENT_DONE, OnPaymentDone)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

CInvoiceView::CInvoiceView()
	: CFormView(CInvoiceView::IDD)
{
	//{{AFX_DATA_INIT(CInvoiceView)
	m_strAmount = _T("");
	//}}AFX_DATA_INIT
}

CInvoiceView::~CInvoiceView()
{
}

void CInvoiceView::DoDataExchange(CDataExchange* pDX)
{
	CFormView::DoDataExchange(pDX);
	//{{AFX_DATA_MAP(CInvoiceView)
	DDX_Control(pDX, IDC_LIST_LINES, m_listLines);
	DDX_Text(pDX, IDC_STATIC_AMOUNT, m_strAmount);
	//}}AFX_DATA_MAP
}

CInvoiceDoc* CInvoiceView::GetDocument()
{
	ASSERT(m_pDocument->IsKindOf(RUNTIME_CLASS(CInvoiceDoc)));
	return (CInvoiceDoc*)m_pDocument;
}

void CInvoiceView::OnInitialUpdate()
{
	CFormView::OnInitialUpdate();
	m_listLines.InsertColumn(0, _T("Item"), LVCFMT_LEFT, 160);
	m_listLines.InsertColumn(1, _T("Qty"), LVCFMT_RIGHT, 50);
	m_listLines.InsertColumn(2, _T("Amount"), LVCFMT_RIGHT, 90);
	FillList();
	UpdateAmountLabel();
}

void CInvoiceView::OnUpdate(CView* pSender, LPARAM lHint, CObject* pHint)
{
	FillList();
	UpdateAmountLabel();
}

void CInvoiceView::FillList()
{
	CInvoiceDoc* pDoc = GetDocument();
	m_listLines.DeleteAllItems();
	for (int i = 0; i < pDoc->m_lines.GetSize(); i++)
	{
		const INVOICELINE& line = pDoc->m_lines[i];
		CString strQty;
		strQty.Format(_T("%d"), line.nQty);
		int nItem = m_listLines.InsertItem(i, line.strItem);
		m_listLines.SetItemText(nItem, 1, strQty);
		m_listLines.SetItemText(nItem, 2, FormatMoney(pDoc->GetLineAmount(i)));
	}
}

void CInvoiceView::UpdateAmountLabel()
{
	CInvoiceDoc* pDoc = GetDocument();
	int nSel = m_listLines.GetNextItem(-1, LVNI_SELECTED);
	double dShown = pDoc->m_dTotal;
	if (nSel >= 0)
		dShown = pDoc->CalcLineAmount(nSel);
	m_strAmount = FormatMoney(dShown);
	SetDlgItemText(IDC_STATIC_AMOUNT, m_strAmount);
}

void CInvoiceView::OnInvoiceRecalc()
{
	GetDocument()->RecalcTotal();
	UpdateAmountLabel();
}

void CInvoiceView::OnItemChangedLines(NMHDR* pNMHDR, LRESULT* pResult)
{
	NM_LISTVIEW* pNMListView = (NM_LISTVIEW*)pNMHDR;
	*pResult = 0;
	if ((pNMListView->uChanged & LVIF_STATE) == 0)
		return;
	if ((pNMListView->uNewState & LVIS_SELECTED) == 0)
		return;
	UpdateAmountLabel();
}

void CInvoiceView::OnInvoicePay()
{
	if (!m_payment.Start(this))
	{
		AfxMessageBox(IDS_SAVE_FAILED);
		return;
	}
	BeginWaitCursor();
}

LRESULT CInvoiceView::OnPaymentDone(WPARAM wParam, LPARAM lParam)
{
	EndWaitCursor();
	int nCount = (int)wParam;
	CString strMsg;
	strMsg.Format(_T("%d payments processed"), nCount);
	AfxMessageBox(strMsg);
	GetDocument()->UpdateAllViews(NULL);
	return 0;
}
