// Customer.cpp : customer master data
#include "stdafx.h"
#include "Customer.h"
#include "../Common/Log.h"

CCustomer::CCustomer()
	: m_nId(0), m_dDefaultDiscount(0.0)
{
}

CCustomer::CCustomer(int nId, const CString& strName, double dDefaultDiscount)
	: m_nId(nId), m_strName(strName), m_dDefaultDiscount(dDefaultDiscount)
{
}

double CCustomer::GetDefaultDiscount() const
{
	if (m_dDefaultDiscount < 0.0)
		return 0.0;
	return m_dDefaultDiscount;
}

CCustomerList::CCustomerList()
{
}

CCustomerList::~CCustomerList()
{
	for (int i = 0; i < m_items.GetSize(); i++)
		delete m_items[i];
	m_items.RemoveAll();
}

void CCustomerList::Load()
{
	m_items.Add(new CCustomer(1, _T("Alpha Trading"), 0.0));
	m_items.Add(new CCustomer(2, _T("Beta Logistics"), 5.0));
	m_items.Add(new CCustomer(3, _T("Gamma Foods"), 12.5));
}

CCustomer* CCustomerList::FindById(int nId)
{
	for (int i = 0; i < m_items.GetSize(); i++)
	{
		CCustomer* pCust = m_items[i];
		if (pCust->GetId() == nId)
			return pCust;
	}
	LOG_ERROR(_T("Customer %d not found"), nId);
	return NULL;
}
