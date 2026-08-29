@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0COLLECT_EVIDENCE.ps1" %*
exit /b %ERRORLEVEL%
