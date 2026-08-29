@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0logs" mkdir "%~dp0logs"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0COLLECT_EVIDENCE.ps1" %* > "%~dp0logs\COLLECT_EVIDENCE.console.log" 2>&1
set "DTVS_EXIT=%ERRORLEVEL%"
type "%~dp0logs\COLLECT_EVIDENCE.console.log"
echo.
echo COLLECT_EVIDENCE exit code: %DTVS_EXIT%
pause
exit /b %DTVS_EXIT%
