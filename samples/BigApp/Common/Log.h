// Log.h : simple file logger
#ifndef BIGAPP_LOG_H
#define BIGAPP_LOG_H

#define LOG_LEVEL_INFO    0
#define LOG_LEVEL_WARN    1
#define LOG_LEVEL_ERROR   2

class CLog
{
public:
	static void Write(int nLevel, const char* pszFile, int nLine, LPCTSTR pszFormat, ...);
	static void SetLevel(int nLevel);
	static int  GetLevel();
private:
	static int  s_nMinLevel;
};

#define LOG_ERROR(fmt, ...) CLog::Write(LOG_LEVEL_ERROR, __FILE__, __LINE__, fmt, __VA_ARGS__)
#define LOG_WARN(fmt, ...)  CLog::Write(LOG_LEVEL_WARN, __FILE__, __LINE__, fmt, __VA_ARGS__)

#endif
