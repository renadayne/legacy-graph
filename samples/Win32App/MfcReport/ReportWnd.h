#pragma once

class CReportWnd : public CWnd
{
public:
    CReportWnd();

protected:
    afx_msg void OnReportPrint();
    afx_msg void OnPaint();
    DECLARE_MESSAGE_MAP()
};

void PrintReport(CWnd* pWnd, int nPages);
