param([string]$Root = "K:\dtvs")
$ErrorActionPreference = "Stop"
& python (Join-Path $PSScriptRoot "scripts\windows_real_pilot.py") run-1min --root $Root
exit $LASTEXITCODE
