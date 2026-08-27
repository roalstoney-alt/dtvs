@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_dtvs_offline_pilot.ps1"
set "DTVS_EXIT=%ERRORLEVEL%"
echo.
if not "%DTVS_EXIT%"=="0" (
  echo DTVS Pilot stopped with exit code %DTVS_EXIT%.
) else (
  echo DTVS Pilot completed.
)
pause
exit /b %DTVS_EXIT%
