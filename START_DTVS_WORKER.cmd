@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set /p "TASK_PACKAGE=Task package path: "
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%dtvs-worker.ps1" doctor
if errorlevel 1 exit /b %errorlevel%
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%dtvs-worker.ps1" run --package "%TASK_PACKAGE%" --workspace "%USERPROFILE%\DTVS"
if errorlevel 1 exit /b %errorlevel%
for /f "tokens=2 delims=:" %%A in ('powershell -NoProfile -Command "$b=Get-Content '%TASK_PACKAGE%' -Raw -ErrorAction SilentlyContinue; Write-Output ''"') do rem noop
powershell -NoProfile -ExecutionPolicy Bypass -Command "$pkg='%TASK_PACKAGE%'; $ws=Join-Path $env:USERPROFILE 'DTVS'; $latest=Get-ChildItem (Join-Path $ws 'runs') -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($latest) { & '%SCRIPT_DIR%dtvs-worker.ps1' export --workspace $ws --run-id $latest.Name --destination (Join-Path $ws 'offline_returns') }"
endlocal
