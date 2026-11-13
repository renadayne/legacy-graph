// LegacyDoc.cpp : implementation of the CLegacyDoc class
//
#include "stdafx.h"
#include "LegacyApp.h"
#include "LegacyDoc.h"
#include "Util.h"

IMPLEMENT_DYNCREATE(CLegacyDoc, CDocument)

BEGIN_MESSAGE_MAP(CLegacyDoc, CDocument)
	ON_COMMAND(ID_TOOLS_RECALC, &CLegacyDoc::OnToolsRecalc)
END_MESSAGE_MAP()

CLegacyDoc::CLegacyDoc()
{
}

CLegacyDoc::~CLegacyDoc()
{
}

BOOL CLegacyDoc::OnNewDocument()
{
	if (!CDocument::OnNewDocument())
		return FALSE;
	m_values.RemoveAll();
	for (int i = 0; i < 10; i++)
		m_values.Add(i * 1.5);
	return TRUE;
}

void CLegacyDoc::Serialize(CArchive& ar)
{
	if (ar.IsStoring())
	{
		ar << (int)m_values.GetSize();
	}
	else
	{
		int n = 0;
		ar >> n;
	}
}

BOOL CLegacyDoc::ExportTo(const CString& strPath, int nFormat, BOOL bOverwrite)
{
	if (!bOverwrite && util::FileExists(strPath))
		return FALSE;

	BOOL bOk = FALSE;
	switch (nFormat)
	{
	case 0:
		bOk = ExportCsv(strPath);
		break;
	case 1:
		bOk = ExportXml(strPath);
		break;
	default:
		ASSERT(FALSE);
	}
	if (bOk)
		util::LogMessage(_T("Export done: ") + strPath);
	return bOk;
}

BOOL CLegacyDoc::ExportCsv(const CString& strPath)
{
	CString text;
	for (int i = 0; i < m_values.GetSize(); i++)
		text += util::FormatNumber(m_values[i]) + _T("\r\n");
	return util::WriteTextFile(strPath, text);
}

BOOL CLegacyDoc::ExportXml(const CString& strPath)
{
	CString text = _T("<values>");
	for (int i = 0; i < m_values.GetSize(); i++)
		text += _T("<v>") + util::FormatNumber(m_values[i]) + _T("</v>");
	text += _T("</values>");
	return util::WriteTextFile(strPath, text);
}

void CLegacyDoc::Recalculate()
{
	for (int i = 0; i < m_values.GetSize(); i++)
		m_values[i] = m_values[i] * 2;
	UpdateAllViews(NULL);
	AfxGetMainWnd()->PostMessage(WM_APP_RECALC_DONE, (WPARAM)m_values.GetSize(), 0);
}

void CLegacyDoc::OnToolsRecalc()
{
	Recalculate();
}
