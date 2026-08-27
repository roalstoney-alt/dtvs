$ErrorActionPreference = "Stop"
param(
  [Parameter(Mandatory=$true)][string]$SourcePath,
  [string]$SegmentStart = "00:10:00.000",
  [int]$DurationSeconds = 1200,
  [string]$Config = "configs/metropolis_20m_v022.json"
)
python scripts/prepare_webm_pilot.py --source $SourcePath --segment-start $SegmentStart --duration $DurationSeconds --config $Config

