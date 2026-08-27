$ErrorActionPreference = "Stop"
param(
  [Parameter(Mandatory=$true)][string]$RunId,
  [string]$Bucket = "dtvs-pilot-assets"
)
python scripts/prepare_r2_upload.py --run-id $RunId --bucket $Bucket
python scripts/upload_tasks_to_r2.py --manifest "runs/$RunId/upload-control/upload_manifest.json" --resume

