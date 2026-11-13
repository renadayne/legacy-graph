// DbConn.h : thin database connection wrapper
#ifndef BIGAPP_DBCONN_H
#define BIGAPP_DBCONN_H

class CDbConnection
{
public:
	CDbConnection();
	~CDbConnection();

	BOOL    Open(const CString& strConnection);
	void    Close();
	BOOL    IsOpen() const { return m_bOpen; }
	BOOL    Execute(const CString& sql);
	CString GetLastError() const { return m_strLastError; }

private:
	BOOL    m_bOpen;
	CString m_strConnection;
	CString m_strLastError;
	int     m_nStatements;
};

extern CDbConnection g_db;

#endif
