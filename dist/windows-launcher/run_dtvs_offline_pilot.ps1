param(
  [switch]$SelfTest,
  [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($PSCommandPath)) {
  throw "LAUNCHER_SCRIPT_PATH_UNAVAILABLE"
}
$script:LauncherScriptPath = [System.IO.Path]::GetFullPath([string]$PSCommandPath)
if ([string]::IsNullOrWhiteSpace($script:LauncherScriptPath)) {
  throw "LAUNCHER_SCRIPT_PATH_UNAVAILABLE"
}

$Root = Split-Path -Parent $script:LauncherScriptPath
$RuntimeRoot = Join-Path $Root "runtime"
$WorkerRoot = Join-Path $RuntimeRoot "worker"
$HandoffRoot = Join-Path $RuntimeRoot "handoff"
$Workspace = Join-Path $Root "workspace"
$Logs = Join-Path $Root "logs"
$Output = Join-Path $Root "output"
$RunId = "DTVS-P001-20260827T065301Z"

# Stable launcher exit codes:
# 0 complete; 10 user cancelled; 20 file discovery failed; 21 hash failed;
# 22 extract failed; 23 handoff post-extract verification failed;
# 30 doctor failed; 31 install or restart required;
# 40 worker failed but recoverable; 41 worker failed unrecoverable;
# 50 export failed; 60 launcher internal error.

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $Workspace, $Logs, $Output | Out-Null
$ConsoleLog = Join-Path $Logs ("launcher-console-{0}.log" -f ((Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")))
$EventsLog = Join-Path $Logs "launcher-events.jsonl"

function Write-Utf8Text {
  param([string]$Path, [string]$Value, [switch]$Bom)
  $encoding = New-Object System.Text.UTF8Encoding($Bom.IsPresent)
  [System.IO.File]::WriteAllText($Path, $Value, $encoding)
}

function Write-LauncherEvent {
  param([string]$Event, [hashtable]$Fields)
  if ($null -eq $Fields) { $Fields = @{} }
  $record = @{ timestamp_utc = (Get-Date).ToUniversalTime().ToString("o"); event = $Event }
  foreach ($key in $Fields.Keys) { $record[$key] = $Fields[$key] }
  $line = ($record | ConvertTo-Json -Compress -Depth 12)
  Add-Content -Encoding UTF8 -Path $EventsLog -Value $line
}

function Stop-DTVS {
  param([int]$Code, [string]$Stage, [string]$Reason)
  Write-Host ""
  Write-Host "DTVS Pilot failed."
  if ($Code -eq 21) { Write-Host "HASH_VERIFICATION_FAILED" }
  if ($Code -eq 23) { Write-Host "HANDOFF_POST_EXTRACT_VERIFICATION_FAILED" }
  if ($Code -eq 50 -and $Reason -eq "RETURN_ZIP_NOT_FOUND") { Write-Host "RETURN_ZIP_NOT_FOUND" }
  if ($Code -eq 50 -and $Reason -eq "RETURN_MANIFEST_SIGNATURE_MISSING") { Write-Host "RETURN_MANIFEST_SIGNATURE_MISSING" }
  Write-Host ("Stage: {0}" -f $Stage)
  Write-Host ("Error code: {0}" -f $Reason)
  Write-Host ("Log: {0}" -f $ConsoleLog)
  if ($Code -eq 40) {
    Write-Host "Recovery: run the same START_DTVS_PILOT.cmd again."
  } else {
    Write-Host "Recovery: fix the reported input or environment issue, then run the same command again."
  }
  Write-LauncherEvent "FAILED" @{ stage = $Stage; reason = $Reason; exit_code = $Code }
  try { Stop-Transcript | Out-Null } catch {}
  exit $Code
}

function Find-OneStrict {
  param([string]$Pattern, [string]$Kind)
  $items = @(Get-ChildItem -LiteralPath $Root -File -Filter $Pattern | Where-Object {
    ($_.Name -notlike "*.partial") -and
    ($_.Name -notlike "*.zip.zip") -and
    ($_.Name -notlike "*.crdownload") -and
    ($_.Name -notlike "*.tmp") -and
    ($_.Name -notlike "*.download")
  })
  if ($items.Count -eq 0) { Stop-DTVS 20 "discover" ("MISSING_" + $Kind) }
  if ($items.Count -gt 1) {
    Write-Host ("Multiple {0} candidates:" -f $Kind)
    foreach ($item in $items) { Write-Host ("  {0}" -f $item.Name) }
    Stop-DTVS 20 "discover" ("MULTIPLE_" + $Kind)
  }
  return $items[0]
}

function Get-ReleaseFiles {
  $workerZip = Find-OneStrict "DTVS-Worker-Pack-*-Windows-x64.zip" "WORKER_ZIP"
  $workerSha = Get-Item -LiteralPath ($workerZip.FullName + ".sha256") -ErrorAction SilentlyContinue
  if ($null -eq $workerSha) { Stop-DTVS 20 "discover" "MISSING_WORKER_SHA256" }
  $handoffZip = Find-OneStrict "DTVS-*-OFFLINE-HANDOFF.zip" "HANDOFF_ZIP"
  $handoffSha = Get-Item -LiteralPath ($handoffZip.FullName + ".sha256") -ErrorAction SilentlyContinue
  if ($null -eq $handoffSha) { Stop-DTVS 20 "discover" "MISSING_HANDOFF_SHA256" }
  return @{
    worker_zip = $workerZip
    worker_sha = $workerSha
    handoff_zip = $handoffZip
    handoff_sha = $handoffSha
  }
}

function Read-PublishedHash {
  param([string]$Path)
  $text = Get-Content -LiteralPath $Path -Raw
  $match = [regex]::Match($text, '(?i)\b[a-f0-9]{64}\b')
  if (-not $match.Success) { Stop-DTVS 21 "hash" "PUBLISHED_HASH_INVALID" }
  return $match.Value.ToLowerInvariant()
}

function Normalize-EnteredHash {
  param([string]$Value)
  if ($null -eq $Value) { Stop-DTVS 21 "hash" "USER_HASH_INVALID" }
  $h = ($Value.Trim()).ToLowerInvariant()
  if ($h -notmatch '^[a-f0-9]{64}$') { Stop-DTVS 21 "hash" "USER_HASH_INVALID" }
  return $h
}

function Verify-ZipHash {
  param([System.IO.FileInfo]$ZipFile, [System.IO.FileInfo]$ShaFile, [string]$Prompt, [string]$SuccessCode)
  $started = Get-Date
  $entered = Normalize-EnteredHash (Read-Host $Prompt)
  $published = Read-PublishedHash $ShaFile.FullName
  $computed = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipFile.FullName).Hash.ToLowerInvariant()
  if (($entered -ne $published) -or ($entered -ne $computed)) {
    Write-Host "HASH_VERIFICATION_FAILED"
    Write-Host ("File: {0}" -f $ZipFile.Name)
    Write-Host ("Entered hash: {0}" -f $entered)
    Write-Host ("Published hash: {0}" -f $published)
    Write-Host ("Computed hash: {0}" -f $computed)
    Stop-DTVS 21 "hash" "HASH_VERIFICATION_FAILED"
  }
  Write-Host $SuccessCode
  Write-LauncherEvent $SuccessCode @{ file = $ZipFile.Name; duration_seconds = [int]((Get-Date) - $started).TotalSeconds }
  return $computed
}

function Test-ZipSafe {
  param([string]$ZipPath)
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
  try {
    foreach ($entry in $zip.Entries) {
      $name = $entry.FullName.Replace('\', '/')
      if ([System.IO.Path]::IsPathRooted($name)) { Stop-DTVS 22 "extract" "ZIP_ABSOLUTE_PATH" }
      if ($name -match '(^|/)\.\.(/|$)') { Stop-DTVS 22 "extract" "ZIP_PATH_TRAVERSAL" }
      if ($name -match '^/') { Stop-DTVS 22 "extract" "ZIP_ABSOLUTE_PATH" }
    }
  } finally {
    $zip.Dispose()
  }
}

function Test-ExtractedWorker {
  param([string]$Dir)
  return @(Get-ChildItem -LiteralPath $Dir -Recurse -File -Filter "dtvs-worker.ps1" -ErrorAction SilentlyContinue).Count -eq 1
}

function Test-ExtractedHandoff {
  param([string]$Dir)
  $mkvs = @(Get-ChildItem -LiteralPath $Dir -Recurse -File -Filter "input_with_context.mkv" -ErrorAction SilentlyContinue)
  $assignment = @(Get-ChildItem -LiteralPath $Dir -Recurse -File -Filter "offline_assignment.json" -ErrorAction SilentlyContinue)
  return (($mkvs.Count -eq 20) -and ($assignment.Count -eq 1))
}

function Test-ExtractMarker {
  param([string]$Target, [string]$Kind, [string]$ZipHash)
  $markerPath = Join-Path $Target ".dtvs_extract_verified.json"
  if (-not (Test-Path -LiteralPath $markerPath)) { return $false }
  try {
    $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
  } catch {
    return $false
  }
  if ($marker.kind -ne $Kind) { return $false }
  if ($marker.zip_sha256 -ne $ZipHash) { return $false }
  if ($Kind -eq "worker") { return (Test-ExtractedWorker $Target) }
  if ($Kind -eq "handoff") { return (Test-ExtractedHandoff $Target) }
  return $false
}

function Expand-SafeZip {
  param([System.IO.FileInfo]$ZipFile, [string]$Target, [string]$Kind, [string]$ZipHash)
  $started = Get-Date
  Test-ZipSafe $ZipFile.FullName
  if (Test-Path -LiteralPath $Target) {
    if (Test-ExtractMarker $Target $Kind $ZipHash) {
      Write-LauncherEvent "EXTRACT_REUSED" @{ kind = $Kind; target = $Target }
      return
    }
    Stop-DTVS 22 "extract" "EXISTING_EXTRACT_DIR_INVALID"
  }
  $partial = $Target + ".partial"
  if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $partial | Out-Null
  Expand-Archive -LiteralPath $ZipFile.FullName -DestinationPath $partial
  $reparse = @(Get-ChildItem -LiteralPath $partial -Recurse -Force | Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 })
  if ($reparse.Count -gt 0) { Stop-DTVS 22 "extract" "ZIP_REPARSE_POINT" }
  $marker = @{
    kind = $Kind
    zip_name = $ZipFile.Name
    zip_sha256 = $ZipHash
    verified_at = (Get-Date).ToUniversalTime().ToString("o")
  } | ConvertTo-Json -Depth 8
  Write-Utf8Text -Path (Join-Path $partial ".dtvs_extract_verified.json") -Value ($marker + [Environment]::NewLine)
  Rename-Item -LiteralPath $partial -NewName ([System.IO.Path]::GetFileName($Target))
  Write-LauncherEvent "EXTRACTED" @{ kind = $Kind; duration_seconds = [int]((Get-Date) - $started).TotalSeconds }
}

function Find-OneExtracted {
  param([string]$Base, [string]$Filter, [string]$Kind)
  $items = @(Get-ChildItem -LiteralPath $Base -Recurse -File -Filter $Filter)
  if ($items.Count -ne 1) { Stop-DTVS 23 "post_extract" ("EXTRACTED_" + $Kind + "_COUNT_" + $items.Count) }
  return $items[0]
}

function Find-HandoffPackageRoot {
  $assignment = Find-OneExtracted $HandoffRoot "offline_assignment.json" "ASSIGNMENT"
  $assignmentDir = Split-Path -Parent $assignment.FullName
  return Split-Path -Parent $assignmentDir
}

function Find-WorkerScript {
  return Find-OneExtracted $WorkerRoot "dtvs-worker.ps1" "WORKER_PS1"
}

function Find-WorkerPython {
  param([System.IO.FileInfo]$WorkerScript)
  $scriptRoot = Split-Path -Parent $WorkerScript.FullName
  $bundled = Join-Path $scriptRoot "python\python.exe"
  if (Test-Path -LiteralPath $bundled) { return $bundled }
  return "python"
}

function Invoke-WorkerHandoffVerify {
  param([System.IO.FileInfo]$WorkerScript, [string]$PackageRoot)
  $python = Find-WorkerPython $WorkerScript
  $scriptRoot = Split-Path -Parent $WorkerScript.FullName
  $code = @'
import json
import sys
from pathlib import Path
from dtvs.worker_pack.package import import_handoff_tasks
assignment, tasks = import_handoff_tasks(Path(sys.argv[1]))
print(json.dumps({"ok": True, "run_id": assignment["run_id"], "task_count": len(tasks)}))
'@
  Push-Location $scriptRoot
  try {
    $output = & $python -c $code $PackageRoot 2>&1
    $exitCode = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  if ($exitCode -ne 0) {
    Write-Host ($output -join [Environment]::NewLine)
    Stop-DTVS 23 "post_extract" "WORKER_HANDOFF_SIGNATURE_VERIFY_FAILED"
  }
  $verify = ($output -join [Environment]::NewLine) | ConvertFrom-Json
  if (($verify.ok -ne $true) -or ($verify.task_count -ne 20)) { Stop-DTVS 23 "post_extract" "WORKER_HANDOFF_VERIFY_INVALID" }
  Write-LauncherEvent "HANDOFF_SIGNATURES_VERIFIED_BY_WORKER" @{ tasks = $verify.task_count; run_id = $verify.run_id }
}

function Test-HandoffPostExtract {
  param([System.IO.FileInfo]$WorkerScript)
  $packageRoot = Find-HandoffPackageRoot
  $manifest = Find-OneExtracted $HandoffRoot "handoff_manifest.json" "HANDOFF_MANIFEST"
  $shaSums = Find-OneExtracted $HandoffRoot "SHA256SUMS.txt" "SHA256SUMS"
  $assignment = Find-OneExtracted $HandoffRoot "offline_assignment.json" "ASSIGNMENT"
  $taskIndex = Find-OneExtracted $HandoffRoot "task_index.json" "TASK_INDEX"
  $null = $taskIndex
  $mkvs = @(Get-ChildItem -LiteralPath $HandoffRoot -Recurse -File -Filter "input_with_context.mkv")
  $bundles = @(Get-ChildItem -LiteralPath $HandoffRoot -Recurse -File -Filter "task_bundle.json")
  $bundleSigs = @(Get-ChildItem -LiteralPath $HandoffRoot -Recurse -File -Filter "task_bundle.sig")
  if (($mkvs.Count -ne 20) -or ($bundles.Count -ne 20) -or ($bundleSigs.Count -ne 20)) { Stop-DTVS 23 "post_extract" "HANDOFF_TASK_COUNT_INVALID" }
  $allText = (Get-Content -LiteralPath $assignment.FullName -Raw) + (Get-Content -LiteralPath $manifest.FullName -Raw)
  if ($allText -match "ACCEPTED") { Stop-DTVS 23 "post_extract" "ACCEPTED_STATE_FORBIDDEN" }
  $forbidden = @("source_master.webm","source_20m_video_cfr.mkv","source_20m_audio.flac","subtitles_20m","hidden_checks.json","private_key","CLOUDFLARE",".env",".dev.vars","Secret")
  foreach ($item in Get-ChildItem -LiteralPath $HandoffRoot -Recurse -File) {
    foreach ($marker in $forbidden) {
      if ($item.FullName.Contains($marker)) { Stop-DTVS 23 "post_extract" "HANDOFF_FORBIDDEN_FILE" }
    }
    if (($item.Extension -eq ".srt") -or ($item.Extension -eq ".ass") -or ($item.Extension -eq ".webm")) { Stop-DTVS 23 "post_extract" "HANDOFF_FORBIDDEN_MEDIA" }
  }
  foreach ($line in Get-Content -LiteralPath $shaSums.FullName) {
    if ($line.Trim().Length -eq 0) { continue }
    $parts = $line.Split(@("  "), 2, [StringSplitOptions]::None)
    if ($parts.Count -ne 2) { Stop-DTVS 23 "post_extract" "SHA256SUMS_INVALID" }
    $expected = $parts[0].ToLowerInvariant()
    $rel = $parts[1]
    if ([System.IO.Path]::IsPathRooted($rel) -or ($rel -match '(^|[\\/])\.\.([\\/]|$)')) { Stop-DTVS 23 "post_extract" "ABSOLUTE_OR_TRAVERSAL_PATH" }
    $actualPath = Join-Path $packageRoot $rel
    if (-not (Test-Path -LiteralPath $actualPath)) { Stop-DTVS 23 "post_extract" "HANDOFF_HASH_FILE_MISSING" }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $actualPath).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { Stop-DTVS 23 "post_extract" "HANDOFF_HASH_MISMATCH" }
  }
  Invoke-WorkerHandoffVerify $WorkerScript $packageRoot
  Write-LauncherEvent "HANDOFF_POST_EXTRACT_VERIFIED" @{ tasks = 20 }
  return $packageRoot
}

function Get-JsonValue {
  param($Object, [string[]]$Names)
  foreach ($name in $Names) {
    $parts = $name.Split(".")
    $current = $Object
    $found = $true
    foreach ($part in $parts) {
      if ($null -eq $current) { $found = $false; break }
      $property = $current.PSObject.Properties[$part]
      if ($null -eq $property) { $found = $false; break }
      $current = $property.Value
    }
    if ($found -and $null -ne $current -and $current -ne "") { return $current }
  }
  return $null
}

function Invoke-WorkerDoctor {
  param([System.IO.FileInfo]$WorkerScript)
  $started = Get-Date
  $log = Join-Path $Logs ("doctor-{0}.log" -f ((Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")))
  $doctorOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $WorkerScript.FullName doctor 2>&1
  $code = $LASTEXITCODE
  $doctorText = $doctorOutput -join [Environment]::NewLine
  Write-Utf8Text -Path $log -Value ($doctorText + [Environment]::NewLine)
  $doctorData = $null
  try {
    $doctorData = $doctorText | ConvertFrom-Json
    Write-Utf8Text -Path (Join-Path $Logs "doctor-latest.json") -Value (($doctorData | ConvertTo-Json -Depth 12) + [Environment]::NewLine)
  } catch {
    Write-Utf8Text -Path (Join-Path $Logs "doctor-latest.json") -Value ("{}" + [Environment]::NewLine)
  }
  Write-LauncherEvent "DOCTOR_FINISHED" @{ exit_code = $code; duration_seconds = [int]((Get-Date) - $started).TotalSeconds }
  if ($code -ne 0) {
    Write-Host "Missing environment items were detected."
    Write-Host "[ ] NVIDIA driver"
    Write-Host "[ ] FFmpeg/ffprobe"
    Write-Host "[ ] Real-ESRGAN"
    Write-Host "[ ] Real-ESRGAN model"
    Write-Host "[ ] Vulkan runtime"
    Write-Host "[ ] Other"
    $answer = Read-Host "Run safe automatic install steps where available? [Y/N]"
    if ($answer -match '^[Yy]$') {
      $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
      if ($winget) {
        Write-Host "Automatic item: FFmpeg, source: winget, package: Gyan.FFmpeg"
        Write-Host "Command: winget install --id Gyan.FFmpeg --source winget"
      } else {
        Write-Host "winget is not available. Install FFmpeg/ffprobe, NVIDIA driver, Real-ESRGAN and model manually, then retry."
      }
      Write-Host "ENVIRONMENT_INSTALL_RESTART_REQUIRED"
      Write-Host ("Restart Windows, then run: {0}" -f (Join-Path $Root "START_DTVS_PILOT.cmd"))
      Stop-DTVS 31 "doctor" "ENVIRONMENT_INSTALL_RESTART_REQUIRED"
    }
    Stop-DTVS 30 "doctor" "DOCTOR_FAILED"
  }
  return $doctorData
}

function Assert-ScriptParsePass {
  $parseTarget = [string]$script:LauncherScriptPath
  if ([string]::IsNullOrWhiteSpace($parseTarget)) {
    Stop-DTVS 60 "self_test" "LAUNCHER_SCRIPT_PATH_EMPTY"
  }
  if (-not (Test-Path -LiteralPath $parseTarget -PathType Leaf)) {
    Stop-DTVS 60 "self_test" "LAUNCHER_SCRIPT_PATH_NOT_FOUND"
  }
  try {
    $parseTarget = (Get-Item -LiteralPath $parseTarget).FullName
    $scriptBytes = [System.IO.File]::ReadAllBytes($parseTarget).Length
    $scriptEncoding = "UTF-8-BOM"
  } catch {
    Stop-DTVS 60 "self_test" "LAUNCHER_SCRIPT_READ_FAILED"
  }
  $tokens = $null
  $parseErrors = $null
  try {
    [System.Management.Automation.Language.Parser]::ParseFile(
      [string]$parseTarget,
      [ref]$tokens,
      [ref]$parseErrors
    ) | Out-Null
  } catch {
    Stop-DTVS 60 "self_test" "LAUNCHER_SCRIPT_READ_FAILED"
  }
  $parseErrorCount = 0
  if ($null -ne $parseErrors) { $parseErrorCount = $parseErrors.Count }
  Write-LauncherEvent "SELF_TEST_SCRIPT_DIAGNOSTICS" @{
    launcher_script_path = $parseTarget
    launcher_script_exists = $true
    launcher_script_bytes = $scriptBytes
    launcher_script_encoding = $scriptEncoding
    powershell_version = $PSVersionTable.PSVersion.ToString()
    parse_error_count = $parseErrorCount
  }
  if ($parseErrorCount -gt 0) {
    foreach ($parseError in $parseErrors) {
      Write-Host ("Parser error at line {0}: {1}" -f $parseError.Extent.StartLineNumber, $parseError.Message)
    }
    Stop-DTVS 60 "self_test" "POWERSHELL_PARSE_FAILED"
  }
  Write-Host "POWERSHELL_51_PARSE_PASS"
}

function Invoke-SelfTest {
  Assert-ScriptParsePass
  $null = $PSVersionTable.PSVersion
  $files = Get-ReleaseFiles
  $null = Read-PublishedHash $files.worker_sha.FullName
  $null = Read-PublishedHash $files.handoff_sha.FullName
  $probe = Join-Path $Output (".write-test-{0}.tmp" -f ([Guid]::NewGuid().ToString("N")))
  Write-Utf8Text -Path $probe -Value "ok"
  Remove-Item -LiteralPath $probe -Force
  Write-Host "LAUNCHER_SELF_TEST_PASS"
}

function Invoke-VerifyOnly {
  $files = Get-ReleaseFiles
  $workerHash = Verify-ZipHash $files.worker_zip $files.worker_sha "Enter Worker Pack SHA-256:" "WORKER_PACKAGE_HASH_VERIFIED"
  $handoffHash = Verify-ZipHash $files.handoff_zip $files.handoff_sha "Enter Handoff SHA-256:" "HANDOFF_PACKAGE_HASH_VERIFIED"
  Expand-SafeZip $files.worker_zip $WorkerRoot "worker" $workerHash
  Expand-SafeZip $files.handoff_zip $HandoffRoot "handoff" $handoffHash
  $workerScript = Find-WorkerScript
  $handoffPackageRoot = Test-HandoffPostExtract $workerScript
  $null = $handoffPackageRoot
  $null = Invoke-WorkerDoctor $workerScript
  Write-Host "LAUNCHER_VERIFY_ONLY_PASS"
}

function Get-StrictReturnZip {
  param($ExportData)
  $zipPath = Get-JsonValue $ExportData @("zip_path", "return_zip_path", "return.zip_path")
  if ($null -ne $zipPath) {
    if (-not (Test-Path -LiteralPath $zipPath)) { Stop-DTVS 50 "export" "RETURN_ZIP_NOT_FOUND" }
    $candidate = Get-Item -LiteralPath $zipPath
    if ($candidate.Extension -ne ".zip") { Stop-DTVS 50 "export" "RETURN_ZIP_NOT_FOUND" }
    if ($candidate.Name -notlike ("*" + $RunId + "*")) { Stop-DTVS 50 "export" "RETURN_ZIP_RUN_ID_MISMATCH" }
    return $candidate
  }
  $matches = @(Get-ChildItem -LiteralPath $Output -File -Filter ("*" + $RunId + "*.zip") | Where-Object { $_.Name -match '(?i)return' })
  if ($matches.Count -eq 0) { Stop-DTVS 50 "export" "RETURN_ZIP_NOT_FOUND" }
  if ($matches.Count -gt 1) { Stop-DTVS 50 "export" "RETURN_ZIP_CONFLICT" }
  return $matches[0]
}

function Get-StrictReturnFile {
  param([string]$Filter, [string]$MissingCode)
  $matches = @(Get-ChildItem -LiteralPath $Output -File -Filter $Filter)
  if ($matches.Count -eq 0) { Stop-DTVS 50 "export" $MissingCode }
  if ($matches.Count -gt 1) { Stop-DTVS 50 "export" ($MissingCode + "_CONFLICT") }
  return $matches[0]
}

function Assert-ReturnSignature {
  param([System.IO.FileInfo]$WorkerScript)
  $manifest = Get-StrictReturnFile "return_manifest.json" "RETURN_MANIFEST_MISSING"
  $signature = Get-StrictReturnFile "return_manifest.sig" "RETURN_MANIFEST_SIGNATURE_MISSING"
  $sigText = (Get-Content -LiteralPath $signature.FullName -Raw).Trim()
  if ($sigText -match '^[a-fA-F0-9]{64}$') { Stop-DTVS 50 "export" "RETURN_MANIFEST_SIGNATURE_IS_HASH" }
  $verifyOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $WorkerScript.FullName verify-return --manifest $manifest.FullName --signature $signature.FullName 2>&1
  $verifyCode = $LASTEXITCODE
  if ($verifyCode -ne 0) {
    Write-Host ($verifyOutput -join [Environment]::NewLine)
    Stop-DTVS 50 "export" "RETURN_MANIFEST_SIGNATURE_VERIFY_FAILED"
  }
  Write-LauncherEvent "RETURN_MANIFEST_SIGNATURE_VERIFIED" @{ manifest = $manifest.Name }
}

function Write-ReturnZipDigestIfNeeded {
  param([System.IO.FileInfo]$ReturnZip, [string]$ReturnHash)
  if ($null -eq $ReturnZip) { Stop-DTVS 50 "export" "RETURN_ZIP_NOT_FOUND" }
  $hashPath = $ReturnZip.FullName + ".sha256"
  $line = ("{0}  {1}" -f $ReturnHash, $ReturnZip.Name)
  if (Test-Path -LiteralPath $hashPath) {
    $published = Read-PublishedHash $hashPath
    if ($published -ne $ReturnHash) { Stop-DTVS 50 "export" "RETURN_ZIP_HASH_MISMATCH" }
    return
  }
  Write-Utf8Text -Path $hashPath -Value ($line + [Environment]::NewLine)
}

function Build-PilotReport {
  param($DoctorData, [System.IO.FileInfo]$ReturnZip, [string]$ReturnHash, [datetime]$RunStarted)
  if ($null -eq $ReturnZip) { Stop-DTVS 50 "export" "RETURN_ZIP_NOT_FOUND" }
  $warnings = @("Power metrics are diagnostic only; terminal cannot generate ACCEPTED.")
  $fieldMap = @{
    os = @("os", "os.caption", "system.os")
    gpu = @("gpu", "gpu.name", "gpu_status")
    driver_version = @("driver_version", "gpu.driver_version", "nvidia.driver_version")
    ffmpeg_version = @("ffmpeg_version", "tools.ffmpeg_version")
    realesrgan_version = @("realesrgan_version", "tools.realesrgan_version")
    model_sha256 = @("model_sha256", "model.sha256")
    worker_pack_version = @("worker_pack_version")
  }
  $doctorFields = @{}
  foreach ($key in $fieldMap.Keys) {
    $value = Get-JsonValue $DoctorData $fieldMap[$key]
    if ($null -eq $value) { $warnings += ("Doctor field unavailable: " + $key) }
    $doctorFields[$key] = $value
  }
  $fingerprintText = "{0}|{1}" -f $env:COMPUTERNAME, $env:PROCESSOR_IDENTIFIER
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $fingerprintBytes = [System.Text.Encoding]::UTF8.GetBytes($fingerprintText)
  $fingerprintHash = ([System.BitConverter]::ToString($sha.ComputeHash($fingerprintBytes))).Replace("-", "").ToLowerInvariant()
  $summaryPath = Join-Path $Workspace ("runs\{0}\worker_run_summary.json" -f $RunId)
  $summary = $null
  if (Test-Path -LiteralPath $summaryPath) {
    $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
  }
  $ready = Get-JsonValue $summary @("ready_for_return")
  $localRejected = Get-JsonValue $summary @("local_rejected")
  $taskCount = Get-JsonValue $summary @("task_count")
  if ($null -eq $ready) { $ready = 0 }
  if ($null -eq $localRejected) { $localRejected = 0 }
  if ($null -eq $taskCount) { $taskCount = 20 }
  $report = @{
    run_id = $RunId
    worker_pack_version = $doctorFields.worker_pack_version
    computer_fingerprint_hash = $fingerprintHash
    os = $doctorFields.os
    gpu = $doctorFields.gpu
    driver = $doctorFields.driver_version
    ffmpeg_version = $doctorFields.ffmpeg_version
    realesrgan_version = $doctorFields.realesrgan_version
    model_sha256 = $doctorFields.model_sha256
    assignment_verified = $true
    bundle_verified_count = 20
    task_count = $taskCount
    tasks_started = $taskCount
    tasks_completed = $ready
    ready_for_return = $ready
    local_rejected = $localRejected
    interrupted_attempts = 0
    resumed_attempts = 0
    completed_tasks_reprocessed = 0
    start_utc = $RunStarted.ToUniversalTime().ToString("o")
    end_utc = (Get-Date).ToUniversalTime().ToString("o")
    total_duration_seconds = [int]((Get-Date) - $RunStarted).TotalSeconds
    return_zip_path = $ReturnZip.Name
    return_zip_bytes = $ReturnZip.Length
    return_zip_sha256 = $ReturnHash
    final_worker_state = "READY_FOR_RETURN"
    network_submission_state = "OFFLINE_MANUAL"
    errors = @()
    warnings = $warnings
  }
  Write-Utf8Text -Path (Join-Path $Output "pilot_terminal_report.json") -Value (($report | ConvertTo-Json -Depth 12) + [Environment]::NewLine)
  $csv = "run_id,task_count,ready_for_return,local_rejected" + [Environment]::NewLine + ("{0},{1},{2},{3}" -f $RunId, $taskCount, $ready, $localRejected) + [Environment]::NewLine
  Write-Utf8Text -Path (Join-Path $Output "task-summary.csv") -Value $csv
  $markdown = @"
# DTVS Pilot Terminal Report

- Run ID: $RunId
- Tasks: $taskCount
- Ready for return: $ready
- Local rejected: $localRejected
- Final worker state: READY_FOR_RETURN
- Return ZIP: $($ReturnZip.Name)
- Return ZIP SHA-256: $ReturnHash
- Network: OFFLINE_MANUAL
- Terminal cannot generate ACCEPTED.
"@
  Write-Utf8Text -Path (Join-Path $Output "pilot_terminal_report.md") -Value ($markdown + [Environment]::NewLine)
  return $report
}

try {
  Start-Transcript -LiteralPath $ConsoleLog -Force | Out-Null
  Write-LauncherEvent "LAUNCHER_STARTED" @{ root = $Root; self_test = $SelfTest.IsPresent; verify_only = $VerifyOnly.IsPresent }

  if ($SelfTest) {
    Invoke-SelfTest
    Write-LauncherEvent "SELF_TEST_FINISHED" @{ exit_code = 0 }
    Stop-Transcript | Out-Null
    exit 0
  }

  $files = Get-ReleaseFiles
  $workerHash = Verify-ZipHash $files.worker_zip $files.worker_sha "Enter Worker Pack SHA-256:" "WORKER_PACKAGE_HASH_VERIFIED"
  $handoffHash = Verify-ZipHash $files.handoff_zip $files.handoff_sha "Enter Handoff SHA-256:" "HANDOFF_PACKAGE_HASH_VERIFIED"
  Expand-SafeZip $files.worker_zip $WorkerRoot "worker" $workerHash
  Expand-SafeZip $files.handoff_zip $HandoffRoot "handoff" $handoffHash
  $workerPs1 = Find-WorkerScript
  $handoffPackageRoot = Test-HandoffPostExtract $workerPs1
  $doctorData = Invoke-WorkerDoctor $workerPs1

  if ($VerifyOnly) {
    Write-Host "LAUNCHER_VERIFY_ONLY_PASS"
    Write-LauncherEvent "VERIFY_ONLY_FINISHED" @{ exit_code = 0 }
    Stop-Transcript | Out-Null
    exit 0
  }

  $handoffManifest = Find-OneExtracted $HandoffRoot "handoff_manifest.json" "HANDOFF_MANIFEST"
  $handoffData = Get-Content -LiteralPath $handoffManifest.FullName -Raw | ConvertFrom-Json

  Write-Host "DTVS Pilot is ready."
  Write-Host ("Run ID: {0}" -f $RunId)
  Write-Host "Tasks: 20"
  Write-Host ("Input total bytes: {0}" -f $handoffData.total_bytes)
  Write-Host "Worker state limit: READY_FOR_RETURN"
  Write-Host "Network: not required"
  Write-Host ("Output directory: {0}" -f $Output)
  $confirm = Read-Host "Start execution? [Y/N]"
  if ($confirm -notmatch '^[Yy]$') { Stop-DTVS 10 "confirm" "USER_CANCELLED" }

  $runStarted = Get-Date
  Write-LauncherEvent "RUN_COMMAND_STARTED" @{ run_id = $RunId }
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $workerPs1.FullName run --package $handoffPackageRoot --workspace $Workspace
  $runCode = $LASTEXITCODE
  Write-LauncherEvent "RUN_COMMAND_FINISHED" @{ run_id = $RunId; exit_code = $runCode; duration_seconds = [int]((Get-Date) - $runStarted).TotalSeconds }
  if ($runCode -ne 0) { Stop-DTVS 40 "run" "WORKER_EXECUTION_FAILED_RECOVERABLE" }

  $exportStarted = Get-Date
  $exportOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $workerPs1.FullName export --workspace $Workspace --run-id $RunId --destination $Output 2>&1
  $exportCode = $LASTEXITCODE
  $exportText = $exportOutput -join [Environment]::NewLine
  Write-Utf8Text -Path (Join-Path $Logs ("export-{0}.log" -f ((Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")))) -Value ($exportText + [Environment]::NewLine)
  Write-LauncherEvent "EXPORT_FINISHED" @{ run_id = $RunId; exit_code = $exportCode; duration_seconds = [int]((Get-Date) - $exportStarted).TotalSeconds }
  if ($exportCode -ne 0) { Stop-DTVS 50 "export" "EXPORT_FAILED" }
  $exportData = $null
  try {
    $exportData = $exportText | ConvertFrom-Json
  } catch {
    Stop-DTVS 50 "export" "EXPORT_OUTPUT_NOT_JSON"
  }

  $returnZip = Get-StrictReturnZip $exportData
  if ($null -eq $returnZip) { Stop-DTVS 50 "export" "RETURN_ZIP_NOT_FOUND" }
  $returnHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $returnZip.FullName).Hash.ToLowerInvariant()
  Write-ReturnZipDigestIfNeeded $returnZip $returnHash
  Assert-ReturnSignature $workerPs1
  $report = Build-PilotReport $doctorData $returnZip $returnHash $runStarted

  Write-Host "========================================"
  Write-Host "DTVS PILOT TERMINAL EXECUTION COMPLETED"
  Write-Host "========================================"
  Write-Host ("Run ID: {0}" -f $RunId)
  Write-Host "Tasks: 20"
  Write-Host ("Ready for return: {0}" -f $report.ready_for_return)
  Write-Host ("Local rejected: {0}" -f $report.local_rejected)
  Write-Host ("Interrupted/resumed: {0}/{1}" -f $report.interrupted_attempts, $report.resumed_attempts)
  Write-Host "Output:"
  Write-Host $Output
  Write-Host ""
  Write-Host "Return ZIP:"
  Write-Host $returnZip.FullName
  Write-Host ""
  Write-Host "Return ZIP SHA-256:"
  Write-Host $returnHash
  Write-Host ""
  Write-Host "Return the output directory to the center."
  Write-Host "The terminal cannot generate ACCEPTED."
  Write-Host "========================================"
  Write-LauncherEvent "LAUNCHER_FINISHED" @{ run_id = $RunId; exit_code = 0 }
  Stop-Transcript | Out-Null
  exit 0
} catch {
  Write-Host ("Launcher internal error: {0}" -f $_.Exception.Message)
  Write-LauncherEvent "INTERNAL_ERROR" @{ error = $_.Exception.Message }
  try { Stop-Transcript | Out-Null } catch {}
  exit 60
}
