$ErrorActionPreference = "Stop"

$commands = @("python", "ffmpeg", "ffprobe", "nvidia-smi")
foreach ($cmd in $commands) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $cmd"
    }
}

$tool = "tools/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan.exe"
if (-not (Test-Path $tool)) { throw "Missing Real-ESRGAN executable: $tool" }
if (-not (Test-Path "inputs/source_master.mkv")) { throw "Missing inputs/source_master.mkv" }
if (-not (Test-Path "inputs/subtitles_zh.srt")) { throw "Missing inputs/subtitles_zh.srt" }

python scripts/dtvs_pilot.py preflight --config configs/metropolis_20m.json

