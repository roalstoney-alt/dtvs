#!/usr/bin/env python3
"""DTVS-P001 single-node v0.2.1 baseline runner.

This file is intentionally preserved as the v0.2.1 runner surface. The v0.2.2
implementation lives under the dtvs package and scripts/run_v022_pilot.ps1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path, block: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(block):
            h.update(chunk)
    return h.hexdigest()


def load_config(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = [
        "spec_version",
        "pilot_id",
        "source_path",
        "subtitle_path",
        "segment_start",
        "segment_duration_seconds",
        "chunk_seconds",
        "target_width",
        "target_height",
        "realesrgan_executable",
        "realesrgan_model",
    ]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Missing config fields: {missing}")
    if data["spec_version"] != "0.2.1":
        raise ValueError("dtvs_pilot.py only accepts v0.2.1 config")
    if data["segment_duration_seconds"] != 1200:
        raise ValueError("DTVS-P001 requires exactly 1200 seconds")
    if data["segment_duration_seconds"] % data["chunk_seconds"]:
        raise ValueError("duration must divide evenly by chunk_seconds")
    return data


def preflight(config_path: Path) -> dict:
    cfg = load_config(config_path)
    missing_commands = [cmd for cmd in ("ffmpeg", "ffprobe") if not shutil.which(cmd)]
    result = {
        "checked_at": utc_now(),
        "spec_version": cfg["spec_version"],
        "runner": "v0.2.1",
        "missing_commands": missing_commands,
        "gpu_check": "SKIPPED_WITH_REASON: not required for characterization tests",
        "inputs_present": {
            "source": (ROOT / cfg["source_path"]).exists(),
            "subtitle": (ROOT / cfg["subtitle_path"]).exists(),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def run_pilot(config_path: Path, run_id: str | None) -> int:
    cfg = load_config(config_path)
    run_id = run_id or f"{cfg['pilot_id']}-DRYRUN"
    out = ROOT / "runs" / run_id
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "spec_version": cfg["spec_version"],
        "state": "DESIGN",
        "created_at": utc_now(),
        "note": "v0.2.1 baseline preserved; real media execution requires operator inputs",
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_manifest": str(out / "run_manifest.json")}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        p.add_argument("--run-id")
    args = ap.parse_args()
    config = (ROOT / args.config).resolve()
    if args.command == "preflight":
        preflight(config)
        return 0
    return run_pilot(config, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())

