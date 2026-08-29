@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0logs" mkdir "%~dp0logs"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0VERIFY_INPUTS.ps1" %* > "%~dp0logs\VERIFY_INPUTS.console.log" 2>&1
set "DTVS_EXIT=%ERRORLEVEL%"
type "%~dp0logs\VERIFY_INPUTS.console.log"
echo.
echo VERIFY_INPUTS exit code: %DTVS_EXIT%
pause
exit /b %DTVS_EXIT%
