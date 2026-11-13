// ExportPdf.cpp : レポートのPDF出力
// このファイルはCP932(Shift-JIS)で保存されている。
#include "stdafx.h"
#include "ExportPdf.h"
#include "ReportDoc.h"
#include "../Common/Money.h"
#include "../Common/Log.h"

CReportExporter::CReportExporter()
	: m_pDoc(NULL)
{
}

// ヘッダ部分を書き込む
BOOL CReportExporter::WriteHeader(CFile& file)
{
	const char szHeader[] = "%PDF-1.4\n";
	TRY
	{
		file.Write(szHeader, sizeof(szHeader) - 1);
	}
	CATCH(CFileException, e)
	{
		return FALSE;
	}
	END_CATCH
	return TRUE;
}

BOOL CReportExporter::ExportPdf(const CString& path)
{
	if (m_pDoc == NULL || m_pDoc->GetCount() == 0)
	{
		// 出力するデータがない場合は何もしない
		LOG_ERROR(_T("ExportPdf: no data for %s"), (LPCTSTR)path);
		AfxMessageBox(_T("レポート出力に失敗しました"));
		return FALSE;
	}

	CFile file;
	if (!file.Open(path, CFile::modeCreate | CFile::modeWrite))
	{
		AfxMessageBox(_T("レポート出力に失敗しました"));
		return FALSE;
	}
	if (!WriteHeader(file))
	{
		file.Close();
		return FALSE;
	}
	for (int i = 0; i < m_pDoc->GetCount(); i++)
	{
		CStringA strLine;
		strLine.Format("%d %s\n", i + 1, (LPCSTR)CStringA(FormatMoney(m_pDoc->m_values[i])));
		file.Write((LPCSTR)strLine, strLine.GetLength());
	}
	file.Close();
	return TRUE;
}
