# DTVS Spec v0.2.1 — Single-node Pilot profile

Status: Pilot freeze  
Date: 2026-08-27  
Evidence unit: DTVS-P001  
Parent: DTVS Spec v0.2

## 1. Purpose

This profile converts Spec v0.2 into one executable fact unit: a 20-minute film segment restored to 4K on a single RTX 4060 terminal with Chinese subtitles.

It validates task determinism, checkpointing, evidence capture, local recovery, quality gates, and marginal-cost measurement. It does not validate multi-node scheduling, adversarial nodes, cross-network transfer, or network-scale economics.

## 2. Frozen claim boundary

The Pilot may conclude only whether the specified single-node workflow is reproducible and auditable. It must not claim that:

- distributed compute is faster than centralized compute;
- DTVS is cheaper or more energy efficient before a matched baseline exists;
- the source film or generated master can be commercially distributed;
- a single-node resume test proves automatic cross-node failover;
- PSNR/SSIM alone proves perceptual restoration quality.

## 3. Task Bundle

Every run freezes:

- source path, byte size, SHA-256, ffprobe metadata, and rights note;
- Chinese subtitle SHA-256, encoding, language, authorship/source, and manual review state;
- exact segment start and 1,200-second duration;
- chunk duration, model, scale, tile, filters, codec, CRF, pixel format, and software versions;
- target dimensions, duration tolerance, required subtitle streams, samples, and evidence files;
- run ID, node ID pseudonym, start/end timestamps, and configuration SHA-256.

Changing a frozen field creates a new run ID. Results from different configurations must not be pooled.

## 4. Execution state machine

`CREATED → PREFLIGHT_PASSED → SEGMENT_FROZEN → CHUNK_EXTRACTED → CHUNK_UPSCALED → CHUNK_ENCODED → CHUNK_ACCEPTED → ASSEMBLED → QC_COMPLETE → VERIFIED | FAILED`

Each chunk has its own JSON checkpoint. A chunk is accepted only after the encoded artifact exists, can be probed, has the expected duration range, and has a SHA-256. Re-running the same configuration skips accepted chunks and resumes at the first incomplete chunk.

## 5. Single-node failure tests

Run at least three controlled interruptions:

1. stop the process during frame extraction;
2. stop the process during Real-ESRGAN execution;
3. stop the process after chunk encoding but before final assembly.

For each test record interruption time, last durable state, lost compute time, restart time, repeated work, and whether the final artifact hash/evidence chain remains complete. These are local recovery tests, not node failover tests.

## 6. Subtitle contract

The Chinese SRT is a controlled human-reviewed input. It must use UTF-8, monotonically increasing cue times, no overlapping cues unless documented, and timestamps inside the frozen segment. The evidence bundle records its origin and SHA-256.

The Pilot produces:

- a 4K MKV master with a switchable `zho` subtitle stream;
- a review MP4 with burned Chinese subtitles.

Machine-generated translation may be used only if every cue is manually reviewed and the method is disclosed.

## 7. Verification ladder

Level 0 — integrity: file existence, SHA-256, config hash, software versions.  
Level 1 — structure: codec, 3840×2160, duration, frame rate, stream count, subtitle language.  
Level 2 — process: every chunk checkpoint present, no missing frames, energy log continuous, no unexplained restart.  
Level 3 — objective signals: black/freeze detection, structural-retention SSIM against a matched downscaled output, timing continuity.  
Level 4 — manual sampling: 20 frozen timestamps reviewed for faces, edges, flicker, scratches, intertitles, motion, subtitle timing, and hallucinated texture.  
Level 5 — acceptance: all hard gates pass and all exceptions are disclosed.

SSIM is a structural-drift guard, not proof of visual improvement.

## 8. Measurement boundary

Record GPU energy from `nvidia-smi` power samples and separately record wall energy from a smart plug when available. GPU-only energy must never be labeled full-system energy.

Single-node marginal cost includes electricity, storage growth, manual subtitle/review time, failed work, and optional hardware-wear reserve. Existing hardware purchase cost is reported separately because the idle-resource hypothesis treats it as sunk for the primary-use owner; both views must remain visible.

## 9. Acceptance gates

- exact source, subtitle, and configuration hashes recorded;
- 20 accepted 60-second chunks and zero missing chunks;
- final master 3840×2160 and duration within ±1 second of 1,200 seconds;
- Chinese soft-subtitle stream present and burned review output present;
- every final artifact hashed;
- energy samples and run timestamps available;
- 20 manual samples completed;
- every exception classified; no silent deletion of failed evidence.

Passing these gates changes the run to `VERIFIED`. Any failed hard gate changes it to `FAILED`, even if the video appears watchable.

## 10. Required evidence bundle

`run_manifest.json`, `task_bundle.json`, `source_probe.json`, `software_versions.json`, `energy.csv`, `events.jsonl`, `chunks/*/checkpoint.json`, `qc_report.json`, `manual_review.csv`, `artifact_hashes.json`, and `pilot_summary.md`.

## 11. Transition to Spec v0.3

Spec v0.3 may begin only after the single-node workflow is reproducible. The next profile adds the second RTX 4060, leases, heartbeats, remote artifact transfer, automatic reassignment, duplicate-settlement protection, and cross-node evidence comparison.

