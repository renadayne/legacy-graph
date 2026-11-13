// TaxCalc.h : VAT computation
#ifndef BIGAPP_TAXCALC_H
#define BIGAPP_TAXCALC_H

class CTaxCalculator
{
public:
	static double ComputeVat(double dNet);
	static double ComputeGross(double dNet);
	static double EffectiveRate();
};

#endif
