$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ScriptRoot "python\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
& $Python (Join-Path $ScriptRoot "dtvs_worker_cli.py") @args
exit $LASTEXITCODE

