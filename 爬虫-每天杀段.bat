@echo off
set "PY_CMD="
py -3 --version >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
  python --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
  echo Cannot find Python. Please install Python and add it to PATH.
  pause
  exit /b 1
)
cd /d "%~dp0"
title duan crawler

set "ISSUE="
set /p ISSUE=Input period, example 125: 
if "%ISSUE%"=="" (
  echo No period input. Canceled.
  pause
  exit /b 1
)

set "WORKERS=8"
set "WORKERS_INPUT="
set /p WORKERS_INPUT=Workers? Press Enter for 8: 
if not "%WORKERS_INPUT%"=="" set "WORKERS=%WORKERS_INPUT%"

echo.
echo Running duan crawler for period %ISSUE%...
where py >nul 2>nul
if not errorlevel 1 (
  %PY_CMD% "%~dp0duan_crawler.py" -i %ISSUE% --workers %WORKERS%
) else (
  %PY_CMD% "%~dp0duan_crawler.py" -i %ISSUE% --workers %WORKERS%
)

echo.
echo Finished. Check these files:
echo ..\数据统一归纳\%ISSUE%期-段.txt
echo ..\数据统一归纳\%ISSUE%期-段-失败.txt
pause
