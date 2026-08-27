# DTVS-P001 runbook — 20-minute RTX 4060 film restoration

## Decision before execution

The default segment is `00:10:00–00:30:00`, but the exact source version may differ. Generate a preview and confirm that the frozen 20 minutes include faces, motion, high-contrast edges, dark scenes, intertitles, and at least one difficult motion sequence. If not, change `segment_start` **before** the run and record the reason.

## Rights gate

Do not assume that a downloadable copy is legally reusable. Record separately:

- original film status in the intended territory;
- scan/master owner and license;
- restoration/reconstruction rights;
- music rights;
- subtitle source and translation authorship;
- whether the output is internal evidence only or approved for publication.

If any element is unclear, keep film files and visual samples out of GitHub. Publish only code, hashes, aggregate metrics, and a written rights limitation.

## Hardware

- one Windows terminal with RTX 4060 and current NVIDIA driver;
- minimum 80GB free temporary space; 150GB recommended;
- stable local storage, not a network share;
- optional smart plug for wall-power measurement;
- disable sleep and automatic restart during the run.

## Software

- Python 3.11+;
- FFmpeg/ffprobe 6+ in PATH, built with libx265 and libass;
- `nvidia-smi` in PATH;
- official `realesrgan-ncnn-vulkan` portable build and model files.

## Inputs

Place:

- `inputs/source_master.mkv` — highest legally usable source;
- `inputs/subtitles_zh.srt` — UTF-8, manually reviewed, aligned to the full source timeline; the runner automatically extracts and shifts the frozen segment;
- an optional `inputs/RIGHTS_NOTE.md` — source URL, license evidence, retrieval date, restrictions.

Do not commit inputs.

## Run sequence

1. Review and freeze `configs/metropolis_20m.json`.
2. Run `scripts/preflight.ps1`.
3. Start smart-plug logging if available.
4. Run `scripts/run_pilot.ps1`.
5. During a rehearsal, inject one interruption; during the formal run, perform all three required interruption tests on separate run IDs.
6. Complete `manual_review.csv` at the 20 frozen one-minute samples.
7. Run the evidence command again after manual review.
8. Do not mark `VERIFIED` until every hard gate passes.

## Expected duration

Real-ESRGAN 4× on 20 minutes can require many hours on an RTX 4060. This is acceptable: the Pilot tests the ability to exchange longer completion time for use of an already-owned idle asset. Record actual elapsed time; do not promise a duration before measurement.

## Publishable result

Publish:

- exact tag and commit;
- hashes and software versions;
- configuration;
- total elapsed time, GPU energy, optional wall energy, storage, restarts, and manual labor;
- accepted/rejected chunks and exception reasons;
- aggregate QC and 20-sample review results;
- cost calculation under measured electricity and a disclosed wear reserve;
- limits of the single-node result.

Do not publish the source/master or subtitle text unless rights permit it.
