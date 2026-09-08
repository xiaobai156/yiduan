@echo off
cd /d "%~dp0"
set "FAIL_TXT=%~1"
if not defined FAIL_TXT set /p "FAIL_TXT=Input failure TXT path: "
if not defined FAIL_TXT exit /b 2
set "FAIL_TXT=%FAIL_TXT:"=%"
py -3 --version >nul 2>nul
if errorlevel 1 (
  python -m duan_app.retry_failed "%FAIL_TXT%"
) else (
  py -3 -m duan_app.retry_failed "%FAIL_TXT%"
)
set "RETRY_EXIT=%ERRORLEVEL%"
pause
exit /b %RETRY_EXIT%
