#include "stdafx.h"
#include "ReportWnd.h"

void PrintReport(CWnd* pWnd, int nPages)
{
    CPrintDialog dlg(FALSE);

    if (dlg.DoModal() != IDOK)
        return;
    CDC dc;
    dc.Attach(dlg.GetPrinterDC());
    DOCINFO di = { sizeof(DOCINFO), _T("Report") };
    dc.StartDoc(&di);
    for (int i = 0; i < nPages; i++) {
        dc.StartPage();
        dc.TextOut(100, 100, _T("Report"));
        dc.EndPage();
    }
    dc.EndDoc();
}
