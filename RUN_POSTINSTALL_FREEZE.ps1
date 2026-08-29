param([string]$Root = "K:\dtvs")
$ErrorActionPreference = "Stop"
& python (Join-Path $PSScriptRoot "scripts\windows_real_pilot.py") postinstall-freeze --root $Root
exit $LASTEXITCODE
