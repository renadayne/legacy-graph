// LegacyDoc.h : interface of the CLegacyDoc class
#pragma once

#include <afxtempl.h>

class CLegacyDoc : public CDocument
{
protected: // create from serialization only
	CLegacyDoc();
	DECLARE_DYNCREATE(CLegacyDoc)

// Attributes
public:
	CArray<double, double> m_values;

// Operations
public:
	BOOL ExportTo(const CString& strPath, int nFormat, BOOL bOverwrite);
	BOOL HasData() const { return m_values.GetSize() > 0; }
	void Recalculate();

// Overrides
public:
	virtual BOOL OnNewDocument();
	virtual void Serialize(CArchive& ar);

// Implementation
public:
	virtual ~CLegacyDoc();

private:
	BOOL ExportCsv(const CString& strPath);
	BOOL ExportXml(const CString& strPath);

protected:
	afx_msg void OnToolsRecalc();
	DECLARE_MESSAGE_MAP()
};
