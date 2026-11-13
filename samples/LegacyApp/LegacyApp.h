// LegacyApp.h : main header file for the LegacyApp application
#pragma once

#include "resource.h"

class CLegacyApp : public CWinApp
{
public:
	CLegacyApp();

// Overrides
public:
	virtual BOOL InitInstance();
	virtual int ExitInstance();

// Implementation
	afx_msg void OnAppAbout();
	DECLARE_MESSAGE_MAP()

private:
	int m_nRunCount;
};

extern CLegacyApp theApp;
