param([string]$Root = "K:\dtvs")
$ErrorActionPreference = "Stop"
try { $Python = (Get-Command python -ErrorAction Stop).Source } catch { Write-Error "PYTHON_NOT_FOUND"; exit 60 }
& $Python (Join-Path $PSScriptRoot "scripts\windows_real_pilot.py") verify-inputs --root $Root
exit $LASTEXITCODE
