// Money.cpp : money rounding and formatting helpers
#include "stdafx.h"
#include "Money.h"
#include "Settings.h"
#include <math.h>

double RoundMoney(double dAmount, int nDecimals)
{
	double dScale = 1.0;
	for (int i = 0; i < nDecimals; i++)
		dScale *= 10.0;

	double dScaled = dAmount * dScale;
	if (g_settings.m_nRounding == 1)
		dScaled = ceil(dScaled - 1e-9);
	else
		dScaled = floor(dScaled + 0.5);
	return dScaled / dScale;
}

CString FormatMoney(double dAmount)
{
	// default presentation: two decimals, thousands separated by commas
	long nCents = (long)floor(dAmount * 100.0 + 0.5);
	return FormatMoney(nCents, 2);
}

CString FormatMoney(long nCents, int nDecimals)
{
	BOOL bNegative = nCents < 0;
	if (bNegative)
		nCents = -nCents;

	long nDivisor = 1;
	for (int i = 0; i < nDecimals; i++)
		nDivisor *= 10;
	long nWhole = nCents / nDivisor;
	long nFrac  = nCents % nDivisor;

	CString strWhole;
	strWhole.Format(_T("%ld"), nWhole);
	CString strOut;
	int nLen = strWhole.GetLength();
	for (int j = 0; j < nLen; j++)
	{
		if (j > 0 && (nLen - j) % 3 == 0)
			strOut += _T(',');
		strOut += strWhole[j];
	}
	if (nDecimals > 0)
	{
		CString strFmt;
		strFmt.Format(_T(".%%0%dld"), nDecimals);
		CString strFrac;
		strFrac.Format(strFmt, nFrac);
		strOut += strFrac;
	}
	if (bNegative)
		strOut = _T("-") + strOut;
	return strOut;
}
