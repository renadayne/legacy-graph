// Settings.h : persistent application settings
#ifndef BIGAPP_SETTINGS_H
#define BIGAPP_SETTINGS_H

class CAppSettings
{
public:
	CAppSettings();

	int     m_nVatRate;       // percent, e.g. 10
	int     m_nRounding;      // 0 = nearest, 1 = round up
	CString m_strCompany;
	CString m_strConnection;

	void Load();
	BOOL Save();
};

extern CAppSettings g_settings;

#endif
