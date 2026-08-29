param([string]$Root = "K:\dtvs")
$ErrorActionPreference = "Stop"
& python (Join-Path $PSScriptRoot "scripts\windows_real_pilot.py") verify-inputs --root $Root
exit $LASTEXITCODE
