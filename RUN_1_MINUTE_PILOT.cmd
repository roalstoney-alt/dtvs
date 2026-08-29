@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0logs" mkdir "%~dp0logs"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_1_MINUTE_PILOT.ps1" %* > "%~dp0logs\RUN_1_MINUTE_PILOT.console.log" 2>&1
set "DTVS_EXIT=%ERRORLEVEL%"
type "%~dp0logs\RUN_1_MINUTE_PILOT.console.log"
echo.
echo RUN_1_MINUTE_PILOT exit code: %DTVS_EXIT%
pause
exit /b %DTVS_EXIT%
