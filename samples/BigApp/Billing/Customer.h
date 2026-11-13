// Customer.h : customer master data
#ifndef BIGAPP_CUSTOMER_H
#define BIGAPP_CUSTOMER_H

class CCustomer
{
public:
	CCustomer();
	CCustomer(int nId, const CString& strName, double dDefaultDiscount);

	int     GetId() const { return m_nId; }
	CString GetName() const { return m_strName; }
	double  GetDefaultDiscount() const;

private:
	int     m_nId;
	CString m_strName;
	double  m_dDefaultDiscount;
};

class CCustomerList
{
public:
	CCustomerList();
	~CCustomerList();

	void       Load();
	int        GetCount() const { return m_items.GetSize(); }
	CCustomer* GetAt(int nIndex) const { return m_items[nIndex]; }
	CCustomer* FindById(int nId);

private:
	CArray<CCustomer*, CCustomer*> m_items;
};

#endif
