#include "stdafx.h"
#include "../resource.h"
#include "ReportWnd.h"

BEGIN_MESSAGE_MAP(CReportWnd, CWnd)
    ON_COMMAND(IDM_REPORT_PRINT, OnReportPrint)
    ON_WM_PAINT()
END_MESSAGE_MAP()

CReportWnd::CReportWnd()
{
}

void CReportWnd::OnReportPrint()
{
    PrintReport(this, 1);
}

void CReportWnd::OnPaint()
{
    CPaintDC dc(this);
    CRect rc;

    GetClientRect(&rc);
    dc.DrawText(_T("Report"), -1, &rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
}
