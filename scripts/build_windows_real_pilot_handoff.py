#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import base64
import sys

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
NAME = "DTVS-Windows-Real-Pilot-Handoff-v0.2.0"
sys.path.insert(0, str(ROOT))
from dtvs.contracts.models import FrameRange, TaskBundle
from dtvs.contracts.signing import load_private_key, public_key_bytes, sign_document

SOURCE_SHA256 = "d0760e254956b7a248d4e110683e3b91b4bd818fcb85aa1dee673b08be742b7c"
EXE_SHA256 = "07e49f7cbb4ede01ae4dd4c399d3a7e5846e3d2085c3128eff881e55cb7b1a0c"
PARAM_SHA256 = "35330ececcea33b6c397a72548e788d5d53becee4734c50b7fada36e89f10a86"
BIN_SHA256 = "713ee713b0353afaa27976f0563a64a5043bd70b9bd8936c2e26e25ebcdbcddf"
PARAMETERS_SHA256 = "1456b3824417df78d3aa72372f38730b008a3712114262a310f6f5719a1d5403"


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
        "requirements-windows.txt",
    ]
    for rel in files:
        source, target = ROOT / rel, staging / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    key_paths = sorted((ROOT / "runs").glob("**/center/private/signing_keys/private_key.pem"))
    if len(key_paths) != 1:
        raise SystemExit("CENTER_TASK_SIGNING_KEY_UNAVAILABLE")
    key = load_private_key(key_paths[0])
    plan_dir = staging / "task-plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    refs = []
    for idx in range(12):
        start, end = idx * 150, min((idx + 1) * 150, 1799)
        bundle = TaskBundle(
            task_id=f"DTVS-P001-T{idx + 1:04d}", bundle_version=1, asset_id="sha256:" + SOURCE_SHA256,
            core=FrameRange(start, end), context=FrameRange(start, end),
            input={"path_or_object_key": "input/pilot-source.mp4", "sha256": SOURCE_SHA256},
            execution={"worker_pack_version": "0.2.0-pilot", "pipeline_id": "dtvs.realesrgan-ncnn-vulkan.x4.pilot.v1", "model_sha256": BIN_SHA256, "parameters_sha256": PARAMETERS_SHA256, "random_seed": 20260827, "execution_mode": "real_render", "backend": "ncnn_vulkan", "semantic_model_id": "RealESRGAN_x4plus", "backend_artifact_id": "realesrgan_x4plus_ncnn_vulkan_v0.2.0", "executable_sha256": EXE_SHA256, "param_sha256": PARAM_SHA256, "bin_sha256": BIN_SHA256, "scale": 4, "tile": 64},
            output={"width": 2880, "height": 1920, "fps_num": 30000, "fps_den": 1001, "expected_core_frames": end - start},
            lease={"expires_at": "2099-01-01T00:00:00+00:00", "checkpoint_frames": end - start},
            verification={"upload_threshold": 90, "minimum_component_score": 70},
        ).to_dict()
        signed = sign_document(bundle, key, "dtvs-p001-center")
        name = f"task_bundle_{idx + 1:04d}.json"
        (plan_dir / name).write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        refs.append({"task_id": signed["task_id"], "bundle": f"task-plan/{name}", "start_frame": start, "end_frame_exclusive": end})
    plan = {"schema_version": "0.2.2", "run_id": "DTVS-P001-WIN-1MIN", "backend": "ncnn_vulkan", "execution_mode": "real_render", "source_path": "input/pilot-source.mp4", "source_sha256": SOURCE_SHA256, "public_key_b64": base64.b64encode(public_key_bytes(key)).decode("ascii"), "segments": refs, "worker_pack_version": "0.2.0-pilot"}
    (plan_dir / "real-pilot-task-plan.json").write_text(json.dumps(sign_document(plan, key, "dtvs-p001-center"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (plan_dir / "task_index.json").write_text(json.dumps({"schema_version": "0.2.2", "run_id": plan["run_id"], "public_key": plan["public_key_b64"], "tasks": refs}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (staging / "PILOT_HANDOFF_README_CN.txt").write_text(
        "DTVS Windows Real Video Pilot Handoff v0.2.0-pilot\n\n"
        "This is a pilot handoff, not a formal Worker release or installer.\n"
        "real_render_executor=ncnn_vulkan; formal_release=false; installer=false.\n"
        "Real-ESRGAN executables, models, source video, secrets, and Windows results are not bundled.\n"
        "Run VERIFY_INPUTS.cmd first. Run 10 seconds before the one-minute pilot.\n"
        "After completion run COLLECT_EVIDENCE.cmd. Copy only the two files printed\n"
        "as EVIDENCE_ZIP and EVIDENCE_SHA256_FILE back to the Mac.\n"
        "The Mac environment must not be used to claim Windows PASS.\n",
        encoding="utf-8",
    )
    zip_path = DIST / f"{NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(staging).as_posix())
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
