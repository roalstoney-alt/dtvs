@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_10_SECOND_PILOT.ps1" %*
exit /b %ERRORLEVEL%
