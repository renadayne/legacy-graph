// TaxCalc.cpp : VAT computation
#include "stdafx.h"
#include "TaxCalc.h"
#include "../Common/Settings.h"
#include "../Common/Log.h"

// Tax amounts are rounded half-up to whole currency units (the tax office rule)
static double RoundTo(double v, int nDigits)
{
	double dScale = 1.0;
	while (nDigits-- > 0)
		dScale *= 10.0;
	double dShifted = v * dScale;
	long   nWhole = (long)(dShifted + 0.5);
	if (dShifted < 0)
		nWhole = (long)(dShifted - 0.5);
	return (double)nWhole / dScale;
}

double CTaxCalculator::EffectiveRate()
{
	int nRate = g_settings.m_nVatRate;
	if (nRate < 0)
	{
		LOG_WARN(_T("Negative VAT rate %d treated as zero"), nRate);
		nRate = 0;
	}
	return nRate / 100.0;
}

double CTaxCalculator::ComputeVat(double dNet)
{
	double dRate = g_settings.m_nVatRate / 100.0;
	if (dNet <= 0.0)
		return 0.0;
	return RoundTo(dNet * dRate, 0);
}

double CTaxCalculator::ComputeGross(double dNet)
{
	return dNet + ComputeVat(dNet);
}
