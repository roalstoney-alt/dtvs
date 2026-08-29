@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_POSTINSTALL_FREEZE.ps1" %*
exit /b %ERRORLEVEL%
