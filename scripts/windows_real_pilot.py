#!/usr/bin/env python3
"""Windows-only real pilot coordinator; Mac supports --dry-run only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KNOWN = {
    "realesrgan-x4plus.param": "35330ececcea33b6c397a72548e788d5d53becee4734c50b7fada36e89f10a86",
    "realesrgan-x4plus.bin": "713ee713b0353afaa27976f0563a64a5043bd70b9bd8936c2e26e25ebcdbcddf",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def locate_one(root: Path, name: str) -> Path | None:
    matches = sorted(p for p in root.rglob(name) if p.is_file())
    if len(matches) != 1:
        return None
    return matches[0]


def artifact(path: Path | None, expected: str | None = None) -> dict:
    if not path or not path.is_file():
        return {"exists": False, "path": str(path) if path else None, "hash_matches": False}
    digest = sha256(path)
    return {"exists": True, "path": str(path), "bytes": path.stat().st_size, "sha256": digest, "hash_matches": expected is None or digest == expected}


def verify_inputs(root: Path) -> int:
    stage = root / "runtime" / "env-installer" / "realesrgan-stage-20260827T170159Z" / "realesrgan-ncnn-vulkan-v0.2.0-windows"
    canonical = root / "tools" / "realesrgan-ncnn-vulkan"
    stage_exe, canonical_exe = stage / "realesrgan-ncnn-vulkan.exe", canonical / "realesrgan-ncnn-vulkan.exe"
    stage_param, canonical_param = stage / "models" / "realesrgan-x4plus.param", canonical / "models" / "realesrgan-x4plus.param"
    stage_bin, canonical_bin = stage / "models" / "realesrgan-x4plus.bin", canonical / "models" / "realesrgan-x4plus.bin"
    pairs = [("executable", stage_exe, canonical_exe, None), ("param", stage_param, canonical_param, KNOWN["realesrgan-x4plus.param"]), ("bin", stage_bin, canonical_bin, KNOWN["realesrgan-x4plus.bin"])]
    inventory = {"checked_at": now(), "python": sys.version, "os": platform.platform(), "artifacts": {}}
    same = True
    for label, a, b, expected in pairs:
        left, right = artifact(a, expected), artifact(b, expected)
        inventory["artifacts"][label] = {"known_good_stage": left, "canonical_candidate": right}
        same = same and left.get("exists") and right.get("exists") and left.get("sha256") == right.get("sha256")
    inventory["canonical_runtime"] = str(canonical if same else stage)
    inventory["canonical_selection"] = "CANONICAL_MATCH" if same else "KNOWN_GOOD_STAGE_DIVERGENCE"
    source = root / "input" / "pilot-source.mp4"
    smoke = root / "input" / "mac-smoke-input.png"
    inventory["inputs"] = {"pilot_source": artifact(source), "mac_smoke_input": artifact(smoke, "e8ce0d44bde341cc9fb64ee79bff09c7842b7057ecc90fb4ae041367b622f4e9")}
    inventory["tools"] = {name: bool(shutil.which(name)) for name in ["python", "ffmpeg", "ffprobe", "nvidia-smi", "vulkaninfo"]}
    inventory["workspace_writable"] = os.access(root / "workspace", os.W_OK) if (root / "workspace").exists() else True
    (root / "output").mkdir(parents=True, exist_ok=True)
    (root / "output" / "artifact-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    if not same:
        divergence = {"status": "PATH_DIVERGENCE", "known_good_stage": str(stage), "canonical_candidate": str(canonical), "selected_for_pilot": str(stage), "created_at": now()}
        (root / "output" / "PATH_DIVERGENCE_REPORT.json").write_text(json.dumps(divergence, indent=2) + "\n", encoding="utf-8")
    required = [source, smoke, stage_exe, stage_param, stage_bin]
    return 0 if all(p.is_file() for p in required) and all(inventory["tools"].get(name) for name in ["python", "ffmpeg", "ffprobe", "nvidia-smi"]) else 2


def postinstall_freeze(root: Path) -> int:
    output = root / "output"; output.mkdir(parents=True, exist_ok=True)
    candidates = {name: sorted(p for p in root.rglob(name) if p.is_file()) for name in ["test.jpg", "dtvs-postinstall-test.png"]}
    if any(len(v) != 1 for v in candidates.values()):
        return 2
    records = {name: artifact(paths[0]) for name, paths in candidates.items()}
    exe = locate_one(root / "runtime", "realesrgan-ncnn-vulkan.exe")
    records["executable"] = artifact(exe)
    records["frozen_at"] = now()
    (output / "POST_INSTALL_FREEZE_MANIFEST.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    lines = [f"{v['sha256']}  {Path(v['path']).name}" for v in records.values() if isinstance(v, dict) and v.get("exists")]
    (output / "POST_INSTALL_SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    (output / "POST_INSTALL_RESULT.md").write_text("# Post-install freeze\n\nThis is a post-run evidence supplement; it does not rewrite the original test result.\n", encoding="utf-8")
    return 0


def dry_run(root: Path) -> int:
    print(json.dumps({"platform": platform.system(), "root": str(root), "actions": ["verify-inputs", "postinstall-freeze", "run-10s", "run-1min", "resume-1min", "collect-evidence"], "windows_execution": platform.system() == "Windows", "fixture_fallback": False}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["verify-inputs", "postinstall-freeze", "run-10s", "run-1min", "resume-1min", "collect-evidence"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run or platform.system() != "Windows":
        return dry_run(args.root) if args.dry_run else 3
    if args.action == "verify-inputs": return verify_inputs(args.root)
    if args.action == "postinstall-freeze": return postinstall_freeze(args.root)
    if not (args.root / "input" / "real-pilot-task-plan.json").is_file():
        print("REAL_TASK_PLAN_REQUIRED", file=sys.stderr)
        return 4
    raise SystemExit("REAL_PILOT_ORCHESTRATION_NOT_INCLUDED_IN_THIS_CANDIDATE")


if __name__ == "__main__":
    raise SystemExit(main())
