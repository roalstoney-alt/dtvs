$ErrorActionPreference = "Stop"
param(
  [string]$Config = "configs/metropolis_20m_v022.json"
)
python -m dtvs.cli pilot run --config $Config

