@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RESUME_1_MINUTE_PILOT.ps1" %*
exit /b %ERRORLEVEL%
