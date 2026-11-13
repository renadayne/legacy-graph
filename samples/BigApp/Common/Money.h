// Money.h : money rounding and formatting helpers
#ifndef BIGAPP_MONEY_H
#define BIGAPP_MONEY_H

double  RoundMoney(double dAmount, int nDecimals);
CString FormatMoney(double dAmount);
CString FormatMoney(long nCents, int nDecimals);

#endif
