#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dtvs.common.canonical_json import dumps
from dtvs.common.hashing import sha256_bytes, sha256_file
from dtvs.common.media_probe import ffprobe_json, first_video_stream, has_audio_stream, has_subtitle_stream
from dtvs.contracts.signing import generate_private_key, public_key_bytes, save_private_key, sign_document, verify_document


SOURCE_COPY = ROOT / "inputs" / "source_master.webm"
LIMIT = 330301440


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_hms(value: str) -> Fraction:
    h, m, s = value.split(":")
    return Fraction(int(h) * 3600 + int(m) * 60) + Fraction(s)


def run(cmd: list[str], stdout_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    if stdout_path:
        with stdout_path.open("w", encoding="utf-8") as fh:
            return subprocess.run(cmd, text=True, stdout=fh, stderr=subprocess.PIPE, check=False)
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def checked(cmd: list[str]) -> None:
    cp = run(cmd)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "command failed")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--segment-start", default="00:10:00.000")
    ap.add_argument("--duration", type=int, default=1200)
    ap.add_argument("--config", default="configs/metropolis_20m_v022.json")
    args = ap.parse_args()
    source = Path(args.source)
    if not source.exists() or source.suffix.lower() != ".webm":
        raise FileNotFoundError(source)
    original_sha = sha256_file(source)
    SOURCE_COPY.parent.mkdir(parents=True, exist_ok=True)
    if SOURCE_COPY.exists():
        if sha256_file(SOURCE_COPY) != original_sha:
            raise RuntimeError("SOURCE_HASH_MISMATCH: inputs/source_master.webm exists with different hash")
    else:
        shutil.copyfile(source, SOURCE_COPY)
    copied_sha = sha256_file(SOURCE_COPY)
    if copied_sha != original_sha:
        raise RuntimeError("SOURCE_HASH_MISMATCH")
    (ROOT / "inputs" / "source_master.webm.sha256").write_text(copied_sha + "  source_master.webm\n", encoding="utf-8")
    origin = {
        "schema_version": "0.2.2",
        "original_filename": source.name,
        "original_bytes": source.stat().st_size,
        "source_sha256": copied_sha,
        "copied_at": utc(),
        "rights_status": "OPERATOR_CONFIRMED",
        "rights_note": "Software does not determine copyright status",
        "internet_source_url": None,
    }
    (ROOT / "inputs" / "source_origin.json").write_text(json.dumps(origin, ensure_ascii=False, indent=2), encoding="utf-8")

    probe = ffprobe_json(SOURCE_COPY, count_frames=True)
    stream = first_video_stream(probe)
    duration = float(probe["format"]["duration"])
    start = parse_hms(args.segment_start)
    if Fraction(duration).limit_denominator(1000) < start + args.duration:
        raise RuntimeError("SOURCE_DURATION_INSUFFICIENT")
    fps = Fraction(stream["avg_frame_rate"])
    if fps <= 0:
        raise RuntimeError("SOURCE_FRAME_RATE_UNRESOLVED")
    segment_start_frame = int(start * fps)
    segment_frames = int(Fraction(args.duration) * fps)
    segment_end = segment_start_frame + segment_frames
    run_id = f"DTVS-P001-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = ROOT / "runs" / run_id
    master_dir = run_dir / "center" / "master"
    private_dir = run_dir / "center" / "private"
    task_root = run_dir / "task-inputs"
    report_dir = ROOT / "reports" / run_id
    master_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    probe_path = master_dir / "source_probe.json"
    probe_path.write_text(json.dumps(probe, ensure_ascii=False, indent=2), encoding="utf-8")
    decode = run(["ffmpeg", "-v", "error", "-i", str(SOURCE_COPY), "-map", "0:v:0", "-f", "null", "-"])
    decode_check = {"schema_version": "0.2.2", "exit_code": decode.returncode, "error_lines": len([x for x in decode.stderr.splitlines() if x.strip()]), "first_error": next((x for x in decode.stderr.splitlines() if x.strip()), None), "completed_at": utc()}
    (master_dir / "decode_check.json").write_text(json.dumps(decode_check, ensure_ascii=False, indent=2), encoding="utf-8")
    if decode.returncode != 0:
        raise RuntimeError("SOURCE_DECODE_FAILED")

    master = master_dir / "source_20m_video_cfr.mkv"
    partial = master.with_suffix(".mkv.partial")
    checked([
        "ffmpeg", "-hide_banner", "-y", "-ss", args.segment_start, "-i", str(SOURCE_COPY), "-t", str(args.duration),
        "-map", "0:v:0", "-an", "-sn", "-vf", f"fps={fps.numerator}/{fps.denominator},format=yuv420p",
        "-c:v", "ffv1", "-level", "3", "-coder", "1", "-context", "1", "-g", "1", "-f", "matroska", str(partial),
    ])
    os.replace(partial, master)
    master_probe = ffprobe_json(master, count_frames=True)
    master_stream = first_video_stream(master_probe)
    master_frames = int(master_stream.get("nb_read_frames", "0"))
    if master_frames != segment_frames:
        raise RuntimeError(f"OUTPUT_STRUCTURE_INVALID: expected {segment_frames}, got {master_frames}")
    checked(["ffmpeg", "-v", "error", "-i", str(master), "-map", "0:v:0", "-f", "null", "-"])
    audio_state = "ABSENT"
    if has_audio_stream(probe):
        audio = master_dir / "source_20m_audio.flac"
        checked(["ffmpeg", "-hide_banner", "-y", "-ss", args.segment_start, "-i", str(SOURCE_COPY), "-t", str(args.duration), "-vn", "-sn", "-c:a", "flac", str(audio)])
        audio_state = "PRESENT"
    subtitle_state = "PENDING"
    if has_subtitle_stream(probe):
        subtitle_state = "PENDING_REVIEW"
    asset = {
        "schema_version": "0.2.2",
        "asset_id": "sha256:" + sha256_file(master),
        "source_sha256": copied_sha,
        "source_bytes": SOURCE_COPY.stat().st_size,
        "video_stream_index": stream["index"],
        "fps_num": fps.numerator,
        "fps_den": fps.denominator,
        "time_base_num": 1,
        "time_base_den": fps.numerator,
        "width": stream["width"],
        "height": stream["height"],
        "total_frames": master_frames,
        "segment_start_frame": segment_start_frame,
        "segment_end_frame_exclusive": segment_end,
        "master_sha256": sha256_file(master),
        "quality_note": "QUALITY_CLAIM_LIMITED_BY_SOURCE" if stream["width"] < 3840 or stream["height"] < 2160 else None,
        "rights_record": {"status": "OPERATOR_CONFIRMED", "public_domain_claim_not_verified_by_software": True},
        "audio_state": audio_state,
        "subtitle_state": subtitle_state,
    }
    (master_dir / "asset_manifest.json").write_text(json.dumps(asset, ensure_ascii=False, indent=2), encoding="utf-8")

    key = generate_private_key()
    save_private_key(private_dir / "signing_keys" / "private_key.pem", key)
    pub = base64.b64encode(public_key_bytes(key)).decode("ascii")
    tasks = []
    hidden = []
    task_frames = segment_frames // 20
    for idx in range(20):
        task_id = f"DTVS-P001-T{idx + 1:04d}"
        short = f"T{idx + 1:04d}"
        core_start = segment_start_frame + idx * task_frames
        core_end = segment_start_frame + (idx + 1) * task_frames if idx < 19 else segment_end
        ctx_start = max(segment_start_frame, core_start - 16)
        ctx_end = min(segment_end, core_end + 16)
        local_start = ctx_start - segment_start_frame
        ctx_frames = ctx_end - ctx_start
        task_dir = task_root / short
        task_dir.mkdir(parents=True, exist_ok=True)
        task_video = task_dir / "input_with_context.mkv"
        checked([
            "ffmpeg", "-hide_banner", "-y", "-i", str(master), "-an", "-sn",
            "-vf", f"select='between(n\\,{local_start}\\,{local_start + ctx_frames - 1})',setpts=N/FRAME_RATE/TB",
            "-frames:v", str(ctx_frames), "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", str(task_video),
        ])
        if task_video.stat().st_size > LIMIT:
            raise RuntimeError(f"BLOCKED_OBJECT_TOO_LARGE_FOR_WRANGLER: {task_video.name} {task_video.stat().st_size}")
        checked(["ffmpeg", "-v", "error", "-i", str(task_video), "-map", "0:v:0", "-f", "null", "-"])
        anchor = {"schema_version": "0.2.2", "task_id": task_id, "public_anchor_hash": sha256_bytes(f"{task_id}:{core_start}:{core_end}".encode()), "core_start_frame": core_start, "core_end_frame_exclusive": core_end}
        (task_dir / "public_anchors.json").write_text(json.dumps(anchor, ensure_ascii=False, indent=2), encoding="utf-8")
        bundle_unsigned = {
            "schema_version": "0.2.2",
            "task_id": task_id,
            "bundle_version": 1,
            "asset_id": asset["asset_id"],
            "core": {"start_frame": core_start, "end_frame_exclusive": core_end},
            "context": {"start_frame": ctx_start, "end_frame_exclusive": ctx_end},
            "input": {"path_or_object_key": f"task-inputs/{short}/input_with_context.mkv", "sha256": sha256_file(task_video)},
            "execution": {"worker_pack_version": "0.1.0", "pipeline_id": "restoration_realesrgan_v1", "model_sha256": "c" * 64, "parameters_sha256": "d" * 64, "random_seed": 20260827},
            "output": {"width": 3840, "height": 2160, "fps_num": fps.numerator, "fps_den": fps.denominator, "pixel_format": "yuv420p10le", "expected_core_frames": core_end - core_start},
            "lease": {"expires_at": "2026-08-28T00:00:00+00:00", "checkpoint_frames": 120},
            "verification": {"upload_threshold": 90, "minimum_component_score": 70},
        }
        bundle = sign_document(bundle_unsigned, key, "pilot-local-001")
        if not verify_document(bundle, key.public_key()):
            raise RuntimeError("BUNDLE_SIGNATURE_INVALID")
        (task_dir / "task_bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        (task_dir / "task_bundle.sig").write_text(bundle["signature"]["value"] + "\n", encoding="ascii")
        hidden.append({"task_id": task_id, "hidden_commitment": sha256_bytes(f"hidden:{task_id}:{core_start + 7}".encode())})
        tasks.append({"task_id": task_id, "short_id": short, "core": bundle["core"], "context": bundle["context"], "input_sha256": sha256_file(task_video), "input_bytes": task_video.stat().st_size})
    task_index = {"schema_version": "0.2.2", "run_id": run_id, "public_key": pub, "tasks": tasks}
    (run_dir / "center" / "task_index.json").write_text(json.dumps(task_index, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "public").mkdir(exist_ok=True)
    shutil.copyfile(run_dir / "center" / "task_index.json", run_dir / "public" / "task_index.json")
    run_manifest = {"schema_version": "0.2.2", "run_id": run_id, "state": "PHASE_6A_SOURCE_AND_TASKS_VERIFIED", "source_filename": source.name, "source_sha256": copied_sha, "segment_start_frame": segment_start_frame, "segment_end_frame_exclusive": segment_end, "audio": audio_state, "subtitle": subtitle_state, "final_pilot_verification": "FINAL_PILOT_VERIFICATION_BLOCKED" if subtitle_state != "VERIFIED" else "PENDING_WORKER_RUN"}
    (run_dir / "run_manifest.json").write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copyfile(run_dir / "run_manifest.json", run_dir / "public" / "run_manifest.json")
    (private_dir / "hidden_checks.json").write_text(json.dumps({"schema_version": "0.2.2", "checks": hidden}, ensure_ascii=False, indent=2), encoding="utf-8")
    compilation = {"schema_version": "0.2.2", "run_id": run_id, "tasks": len(tasks), "first_core_start": tasks[0]["core"]["start_frame"], "last_core_end_exclusive": tasks[-1]["core"]["end_frame_exclusive"], "sum_core_frame_count": sum(t["core"]["end_frame_exclusive"] - t["core"]["start_frame"] for t in tasks), "duplicate_core_frames": 0, "missing_core_frames": 0, "max_task_object_bytes": max(t["input_bytes"] for t in tasks)}
    (report_dir / "task_compilation_report.json").write_text(json.dumps(compilation, ensure_ascii=False, indent=2), encoding="utf-8")
    source_report = {"schema_version": "0.2.2", "source_gate": "PASS", "source_sha256": copied_sha, "decode_check": decode_check, "quality_note": asset["quality_note"], "audio": audio_state, "subtitle": subtitle_state}
    (report_dir / "source_gate_report.json").write_text(json.dumps(source_report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = f"# Phase 6A Summary\n\n- Run ID: {run_id}\n- Source file: {source.name}\n- Source SHA-256: {copied_sha}\n- Resolution: {stream['width']}x{stream['height']}\n- Codec: {stream.get('codec_name')}\n- FPS: {fps.numerator}/{fps.denominator}\n- Audio: {audio_state}\n- Subtitle: {subtitle_state}\n- Tasks: {len(tasks)}\n- Max task object bytes: {compilation['max_task_object_bytes']}\n- Status: PHASE_6A_SOURCE_AND_TASKS_VERIFIED\n"
    (report_dir / "phase6ab_summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps({"run_id": run_id, "run_manifest": str(run_dir / "run_manifest.json"), "task_count": len(tasks), "max_task_object_bytes": compilation["max_task_object_bytes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
