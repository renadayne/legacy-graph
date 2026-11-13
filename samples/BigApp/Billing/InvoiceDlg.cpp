// InvoiceDlg.cpp : hôòp thoaòi hóa ðõn
// File này ðýõòc lýu õÒ maÞ CP1258 (Windows Vietnamese) nhý code cuÞ.
//
#include "stdafx.h"
#include "../BigApp.h"
#include "InvoiceDlg.h"
#include "InvoiceDoc.h"
#include "../Common/Money.h"
#include "../Common/Log.h"

CInvoiceDlg::CInvoiceDlg(CInvoiceDoc* pDoc, CWnd* pParent /*=NULL*/)
	: CDialog(CInvoiceDlg::IDD, pParent)
{
	//{{AFX_DATA_INIT(CInvoiceDlg)
	m_dDiscount = 0.0;
	//}}AFX_DATA_INIT
	m_pDoc = pDoc;
}

void CInvoiceDlg::DoDataExchange(CDataExchange* pDX)
{
	CDialog::DoDataExchange(pDX);
	//{{AFX_DATA_MAP(CInvoiceDlg)
	DDX_Control(pDX, IDC_CMB_CUSTOMER, m_cmbCustomer);
	DDX_Text(pDX, IDC_EDIT_DISCOUNT, m_dDiscount);
	DDV_MinMaxDouble(pDX, m_dDiscount, 0.0, 100.0);
	//}}AFX_DATA_MAP
}

BEGIN_MESSAGE_MAP(CInvoiceDlg, CDialog)
	//{{AFX_MSG_MAP(CInvoiceDlg)
	ON_BN_CLICKED(IDC_BTN_RECALC, OnBnClickedRecalc)
	ON_BN_CLICKED(IDC_BTN_CLEAR_DISCOUNT, OnBnClickedClearDiscount)
	ON_CBN_SELCHANGE(IDC_CMB_CUSTOMER, OnCbnSelchangeCustomer)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

BOOL CInvoiceDlg::OnInitDialog()
{
	CDialog::OnInitDialog();
	m_customers.Load();
	for (int i = 0; i < m_customers.GetCount(); i++)
	{
		CCustomer* pCust = m_customers.GetAt(i);
		int nIndex = m_cmbCustomer.AddString(pCust->GetName());
		m_cmbCustomer.SetItemData(nIndex, pCust->GetId());
	}
	m_cmbCustomer.SetCurSel(0);
	m_dDiscount = m_pDoc->m_dDiscount;
	UpdateData(FALSE);
	return TRUE;  // traÒ vêÌ TRUE trýÌ khi ðãòt focus vào control
}

void CInvoiceDlg::OnBnClickedRecalc()
{
	// Ðoòc laòi giá triò ngýõÌi dùng nhâòp, rôÌi tính laòi tôÒng tiêÌn
	if (!UpdateData(TRUE))
		return;
	m_pDoc->ApplyDiscount(m_dDiscount);
	m_pDoc->RecalcTotal();

	CString strTotal = FormatMoney(m_pDoc->m_dTotal);
	SetDlgItemText(IDC_STATIC_AMOUNT, strTotal);
}

void CInvoiceDlg::OnBnClickedClearDiscount()
{
	m_dDiscount = 0;
	UpdateData(FALSE);
	m_pDoc->ApplyDiscount(0.0);
	GetDlgItem(IDC_EDIT_DISCOUNT)->SetFocus();
}

void CInvoiceDlg::OnCbnSelchangeCustomer()
{
	int nSel = m_cmbCustomer.GetCurSel();
	if (nSel == CB_ERR)
		return;
	int nId = (int)m_cmbCustomer.GetItemData(nSel);
	CCustomer* pCustomer = m_customers.FindById(nId);
	if (pCustomer == NULL)
		return;
	m_pDoc->m_nCustomerId = nId;
	m_dDiscount = pCustomer->GetDefaultDiscount();
	UpdateData(FALSE);
}

void CInvoiceDlg::OnOK()
{
	if (!UpdateData(TRUE))
		return;
	m_pDoc->ApplyDiscount(m_dDiscount);
	m_pDoc->RecalcTotal();
	if (!m_pDoc->SaveInvoice())
	{
		AfxMessageBox(_T("Không thêÒ lýu hóa ðõn"));
		return;
	}
	CDialog::OnOK();
}
