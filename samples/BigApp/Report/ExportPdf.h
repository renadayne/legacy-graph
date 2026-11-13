// ExportPdf.h : PDF export of a report
#ifndef BIGAPP_EXPORTPDF_H
#define BIGAPP_EXPORTPDF_H

class CReportDoc;

class CReportExporter
{
public:
	CReportExporter();

	void SetDocument(CReportDoc* pDoc) { m_pDoc = pDoc; }
	BOOL ExportPdf(const CString& path);

private:
	CReportDoc* m_pDoc;
	BOOL        WriteHeader(CFile& file);
};

#endif
