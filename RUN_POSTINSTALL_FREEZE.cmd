@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0logs" mkdir "%~dp0logs"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_POSTINSTALL_FREEZE.ps1" %* > "%~dp0logs\RUN_POSTINSTALL_FREEZE.console.log" 2>&1
set "DTVS_EXIT=%ERRORLEVEL%"
type "%~dp0logs\RUN_POSTINSTALL_FREEZE.console.log"
echo.
echo RUN_POSTINSTALL_FREEZE exit code: %DTVS_EXIT%
pause
exit /b %DTVS_EXIT%
