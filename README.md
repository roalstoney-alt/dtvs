# DTVS — Distributed Task Fulfilment Standard

DTVS is an open specification and reference implementation for converting unreliable idle compute into verifiable task fulfilment.

The coordinator performs high-value interpretation, task compilation, scheduling, and verification. Edge nodes receive bounded deterministic work units, execute them during idle windows, checkpoint progress, and submit evidence. DTVS does **not** assume distributed nodes are faster than a data center. Its economic hypothesis is:

> node incentive + marginal energy + transfer/storage + verification + recomputation + orchestration  
> **is lower than** the fully loaded centralized cost of the same accepted result.

## Pilot 001

The first evidence unit is a 20-minute classic-film restoration on one RTX 4060 terminal:

- verified source and Chinese subtitle inputs;
- 60-second resumable chunks;
- conservative denoise and Real-ESRGAN 4× upscale;
- 3840×2160 HEVC master;
- soft Chinese subtitles in MKV and burned-in review MP4;
- GPU power sampling, runtime, hashes, checkpoint ledger, and QC report;
- no claim of cost, quality, or energy advantage until the evidence bundle is complete.

Read [the Pilot runbook](pilot/METROPOLIS_20M_SINGLE_NODE.md) and [Spec v0.2.1](spec/DTVS_SPEC_v0.2.1_SINGLE_NODE_PILOT.md).

## Repository status

`v0.2.1-pilot-start` — single-node evidence unit. This is not yet a distributed-network validation.

## Quick start on Windows + RTX 4060

1. Install NVIDIA drivers, FFmpeg 6+, Python 3.11+, and the official `realesrgan-ncnn-vulkan` portable release.
2. Put the executable at `tools/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan.exe` and its `models` folder beside it.
3. Put the legally usable film master at `inputs/source_master.mkv`.
4. Create/review `inputs/subtitles_zh.srt`; do not commit copyrighted media or subtitle files.
5. Edit `configs/metropolis_20m.json`, especially `segment_start`.
6. Run PowerShell:

```powershell
./scripts/preflight.ps1
./scripts/run_pilot.ps1
```

Results are written under `runs/<run_id>/`. A failed chunk can be resumed by running the same command again.

## Evidence states

- `DESIGN`: specified but not run;
- `RUNNING`: evidence collection in progress;
- `VERIFIED`: all frozen gates passed;
- `FAILED`: one or more gates failed;
- `EXTERNAL`: independently reproduced outside the origin environment.

## License

Code and specification text are released under Apache-2.0. Film masters, restoration masters, music, and subtitle translations are not covered by this repository license.

