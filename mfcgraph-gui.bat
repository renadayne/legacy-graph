@echo off
rem Opens the optional mfcgraph window. Needs only Python 3.7+ (standard installer, includes tkinter). No pip.
where python >nul 2>nul
if %errorlevel%==0 (python "%~dp0mfcgraph.py" gui %*) else (py "%~dp0mfcgraph.py" gui %*)
if errorlevel 1 pause
