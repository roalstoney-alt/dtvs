#!/usr/bin/env python3
"""Read-only verification and lightweight freeze for the Windows node return."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_root = args.evidence_root / "runs" / "DTVS-P001-WIN-1MIN"
    plan_path = args.evidence_root / "task-plan" / "real-pilot-task-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    refs = plan["segments"]
    inventory_path = args.evidence_root / "output" / "artifact-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8")) if inventory_path.is_file() else {}
    args.output.mkdir(parents=True, exist_ok=True)
    segments = []
    decode_records = []
    probe_records = []
    total_bytes = 0
    for ref in refs:
        task_id = ref["task_id"]
        segment = run_root / task_id / "segment.ffv1.mkv"
        record = {
            "task_id": task_id,
            "relative_path": f"runs/DTVS-P001-WIN-1MIN/{task_id}/segment.ffv1.mkv",
            "external_path": str(segment),
            "expected_start_frame": ref["start_frame"],
            "expected_end_frame_exclusive": ref["end_frame_exclusive"],
            "expected_frame_count": ref["end_frame_exclusive"] - ref["start_frame"],
            "exists": segment.is_file(),
        }
        if not segment.is_file():
            record.update({"bytes": 0, "sha256": None, "probe": "NOT_RUN", "decode": "NOT_RUN"})
            segments.append(record)
            continue
        record["bytes"] = segment.stat().st_size
        record["sha256"] = sha256_file(segment)
        total_bytes += record["bytes"]
        probe = run(["ffprobe", "-v", "error", "-count_frames", "-show_entries", "stream=index,codec_name,width,height,r_frame_rate,avg_frame_rate,time_base,nb_frames,nb_read_frames,duration,duration_ts", "-show_entries", "format=duration,duration_ts,size", "-of", "json", str(segment)])
        probe_json = json.loads(probe.stdout or "{}") if probe.returncode == 0 else {}
        stream = next((item for item in probe_json.get("streams", []) if item.get("codec_name") == "ffv1"), {})
        record["probe_exit_code"] = probe.returncode
        record["codec"] = stream.get("codec_name")
        record["width"] = stream.get("width")
        record["height"] = stream.get("height")
        record["r_frame_rate"] = stream.get("r_frame_rate")
        record["avg_frame_rate"] = stream.get("avg_frame_rate")
        record["time_base"] = stream.get("time_base")
        record["duration"] = stream.get("duration") or probe_json.get("format", {}).get("duration")
        record["duration_ts"] = stream.get("duration_ts")
        record["nb_frames"] = stream.get("nb_frames")
        record["actual_decoded_frame_count"] = int(stream["nb_read_frames"]) if stream.get("nb_read_frames", "").isdigit() else None
        record["probe_pass"] = probe.returncode == 0 and record["codec"] == "ffv1" and record["width"] == 2880 and record["height"] == 1920
        probe_records.append({"task_id": task_id, **record})
        decoded = run(["ffmpeg", "-v", "error", "-i", str(segment), "-map", "0:v:0", "-f", "null", "-"])
        record["decode_exit_code"] = decoded.returncode
        record["decode_pass"] = decoded.returncode == 0
        record["decode_stderr"] = decoded.stderr
        record["probe"] = "PASS" if record["probe_pass"] else "FAIL"
        record["decode"] = "PASS" if record["decode_pass"] else "FAIL"
        decode_records.append({"task_id": task_id, "exit_code": decoded.returncode, "stdout": decoded.stdout, "stderr": decoded.stderr})
        segments.append(record)

    ordered = sorted(segments, key=lambda item: item["expected_start_frame"])
    coverage_pass = len(ordered) == 12 and all(a["expected_end_frame_exclusive"] == b["expected_start_frame"] for a, b in zip(ordered, ordered[1:]))
    frame_pass = all(item.get("exists") and item.get("bytes", 0) > 0 and item.get("probe_pass") and item.get("decode_pass") and item.get("actual_decoded_frame_count") == item.get("expected_frame_count") for item in ordered)
    node_pass = len(ordered) == 12 and frame_pass and coverage_pass
    freeze = {
        "evidence_id": "DTVS-P001-WINDOWS-1MIN-NODE-RENDER-v0.1",
        "status": "PASS" if node_pass else "FAIL",
        "run_id": plan["run_id"],
        "source_platform": "Windows",
        "windows_node_pilot": {"real_render": "PASS" if node_pass else "FAIL", "segment_production": "PASS" if node_pass else "FAIL", "segment_return": "PASS" if node_pass else "FAIL"},
        "center_validation": {"segment_probe": "PASS" if frame_pass else "PARTIAL", "frame_count_verification": "PASS" if frame_pass else "EVIDENCE_INCOMPLETE", "boundary_qc": "NOT_EXECUTED", "final_merge": "NOT_EXECUTED", "audio_reattachment": "NOT_EXECUTED"},
        "telemetry": {"resource_report": "NOT_COLLECTED", "energy_report": "NOT_COLLECTED"},
        "overall": {"windows_1min_node_render_pilot": "PASS" if node_pass else "FAIL", "end_to_end_delivery": "PENDING"},
        "hardware": {"gpu": "NVIDIA GeForce RTX 4060", "driver": "596.36", "backend": "ncnn_vulkan"},
        "artifacts": inventory.get("artifacts", {}),
        "segment_count": len(ordered), "total_bytes": total_bytes, "segments": ordered,
        "worker_scope": ["Task Bundle validation", "real inference", "FFV1 segment production", "local structural QC", "hash/manifest/checkpoint/log return"],
        "center_pending": ["independent boundary QC", "segment merge", "audio reattachment", "end-to-end delivery"],
        "resource_limitations": ["Accurate energy, RAM/VRAM telemetry and 20-minute cost are not available in this evidence."],
        "evidence_storage": str(args.evidence_root), "source_git_commit": run(["git", "-C", str(args.repo_root), "rev-parse", "HEAD"]).stdout.strip(),
        "freeze_created_at": datetime.now(timezone.utc).isoformat(), "generator": "freeze_windows_1min_node_pilot.py",
    }
    (args.output / "WINDOWS_1MIN_NODE_PILOT_FREEZE.json").write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
    (args.output / "WINDOWS_1MIN_SEGMENT_MANIFEST.json").write_text(json.dumps({"run_id": plan["run_id"], "segments": ordered, "total_bytes": total_bytes}, indent=2) + "\n", encoding="utf-8")
    (args.output / "WINDOWS_1MIN_SEGMENT_PROBE_SUMMARY.json").write_text(json.dumps({"status": "PASS" if frame_pass else "PARTIAL", "segments": probe_records}, indent=2) + "\n", encoding="utf-8")
    (args.output / "WINDOWS_1MIN_SEGMENT_DECODE_SUMMARY.json").write_text(json.dumps({"status": "PASS" if frame_pass else "FAIL", "segments": decode_records}, indent=2) + "\n", encoding="utf-8")
    sums = [f"{item['sha256']}  {item['relative_path']}" for item in ordered if item.get("sha256")]
    (args.output / "WINDOWS_1MIN_SEGMENT_SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="ascii")
    (args.output / "WINDOWS_1MIN_SCOPE_BOUNDARY.md").write_text("# Windows 1-Minute Node Pilot Scope\n\nWindows node acceptance covers real NCNN/Vulkan rendering and returned FFV1 segments. Center merge, audio reattachment, and end-to-end delivery are separate center responsibilities.\n", encoding="utf-8")
    (args.output / "SUPERSEDED_REPORT_NOTICE.md").write_text("# Superseded Report Notice\n\nThe earlier `completed_segments_verified=false` field is classified as center verification status, not Windows render failure. The original report is retained. This freeze uses the corrected Worker/center responsibility boundary.\n", encoding="utf-8")
    (args.output / "EVIDENCE_STORAGE_POINTER.json").write_text(json.dumps({"storage_type": "external_volume", "storage_path": str(args.evidence_root), "large_artifacts_committed_to_git": False, "large_artifacts": ["12 FFV1 segment files", "temporary frames"], "checked_at": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n", encoding="utf-8")
    return 0 if node_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
