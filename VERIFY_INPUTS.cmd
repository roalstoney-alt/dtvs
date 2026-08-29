@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0VERIFY_INPUTS.ps1" %*
exit /b %ERRORLEVEL%
