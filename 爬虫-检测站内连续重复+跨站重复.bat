@echo off
cd /d "%~dp0"
title É±¶ÎÖØ¸´¼ì²â

set "PY_CMD="
py -3 --version >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
  python --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
  echo Cannot find Python.
  pause
  exit /b 1
)

set "ISSUE="
set /p ISSUE=Input period, example 152: 
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
echo Running period repetition check for period %ISSUE%...
%PY_CMD% "%~dp0period_repetition_checker.py" --period %ISSUE% --window 10 --workers %WORKERS%

echo.
echo Done.
pause
