$ErrorActionPreference = "Stop"
param(
  [string]$Config = "configs/metropolis_20m_v022.json"
)
Write-Output "Fault injection is configured in $Config and recorded during dtvs pilot run."

