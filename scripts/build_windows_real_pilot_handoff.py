#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
NAME = "DTVS-Windows-Real-Pilot-Handoff-v0.2.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    staging = DIST / NAME
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copytree(ROOT / "dtvs", staging / "dtvs", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    files = [
        "schemas/task_bundle_v022.schema.json",
        "dtvs_worker_cli.py",
        "dtvs-worker.ps1",
        "README.md",
        "VERIFY_INPUTS.ps1", "RUN_POSTINSTALL_FREEZE.ps1", "RUN_10_SECOND_PILOT.ps1",
        "RUN_1_MINUTE_PILOT.ps1", "RESUME_1_MINUTE_PILOT.ps1", "COLLECT_EVIDENCE.ps1",
        "VERIFY_INPUTS.cmd", "RUN_POSTINSTALL_FREEZE.cmd", "RUN_10_SECOND_PILOT.cmd",
        "RUN_1_MINUTE_PILOT.cmd", "RESUME_1_MINUTE_PILOT.cmd", "COLLECT_EVIDENCE.cmd",
        "scripts/windows_real_pilot.py",
        "docs/FAILURE_CODES.md",
        "docs/WINDOWS_REAL_PILOT_HANDOFF_V0.2.0_CN.txt",
        "configs/windows_real_pilot_v020.json",
        "schemas/windows_real_pilot_manifest.schema.json",
    ]
    for rel in files:
        source, target = ROOT / rel, staging / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (staging / "PILOT_HANDOFF_README_CN.txt").write_text(
        "DTVS Windows Real Video Pilot Handoff v0.2.0-pilot\n\n"
        "This is a pilot handoff, not a formal Worker release or installer.\n"
        "real_render_executor=ncnn_vulkan; formal_release=false; installer=false.\n"
        "Real-ESRGAN executables, models, source video, secrets, and Windows results are not bundled.\n"
        "Run VERIFY_INPUTS.cmd first. Run 10 seconds before the one-minute pilot.\n"
        "The Mac environment must not be used to claim Windows PASS.\n",
        encoding="utf-8",
    )
    zip_path = DIST / f"{NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(DIST).as_posix())
    manifest = {
        "schema_version": "0.2.2",
        "handoff_version": "0.2.0-pilot",
        "worker_pack_version": "0.2.0-pilot",
        "real_render_executor": "ncnn_vulkan",
        "formal_release": False,
        "installer": False,
        "target": "Windows x64 RTX 4060 optional pilot node",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "zip": {"filename": zip_path.name, "bytes": zip_path.stat().st_size, "sha256": sha256(zip_path)},
        "windows_pass_claimed": False,
        "mac_baseline_tag": "dtvs-p001-macos-cpu-smoke-v0.1",
        "excluded": ["secrets", "private_keys", "Real-ESRGAN EXE", "model files", "source media", "Windows evidence", "fixture results"],
        "files": [],
    }
    for path in sorted(staging.rglob("*")):
        if path.is_file():
            manifest["files"].append({"relative_path": path.relative_to(staging).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest_path = DIST / f"{NAME}-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (DIST / f"{NAME}.zip.sha256").write_text(f"{manifest['zip']['sha256']}  {zip_path.name}\n", encoding="ascii")
    shutil.rmtree(staging)
    print(json.dumps({"zip": str(zip_path), "sha256": manifest["zip"]["sha256"], "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
