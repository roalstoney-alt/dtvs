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
from dtvs.common.hashing import sha256_file
from dtvs.contracts.signing import verify_document
from dtvs.worker.real_ncnn_executor import NcnnArtifacts, execute_realesrgan_ncnn

KNOWN = {
    "realesrgan-x4plus.param": "35330ececcea33b6c397a72548e788d5d53becee4734c50b7fada36e89f10a86",
    "realesrgan-x4plus.bin": "713ee713b0353afaa27976f0563a64a5043bd70b9bd8936c2e26e25ebcdbcddf",
}
EXE_SHA256 = "07e49f7cbb4ede01ae4dd4c399d3a7e5846e3d2085c3128eff881e55cb7b1a0c"


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
    exe = root / "runtime" / "env-installer" / "realesrgan-stage-20260827T170159Z" / "realesrgan-ncnn-vulkan-v0.2.0-windows" / "realesrgan-ncnn-vulkan.exe"
    records["executable"] = artifact(exe)
    records["model_param"] = artifact(exe.parent / "models" / "realesrgan-x4plus.param", KNOWN["realesrgan-x4plus.param"])
    records["model_bin"] = artifact(exe.parent / "models" / "realesrgan-x4plus.bin", KNOWN["realesrgan-x4plus.bin"])
    records["frozen_at"] = now()
    (output / "POST_INSTALL_FREEZE_MANIFEST.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    lines = [f"{v['sha256']}  {Path(v['path']).name}" for v in records.values() if isinstance(v, dict) and v.get("exists")]
    (output / "POST_INSTALL_SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    (output / "POST_INSTALL_RESULT.md").write_text("# Post-install freeze\n\nThis is a post-run evidence supplement; it does not rewrite the original test result.\n", encoding="utf-8")
    return 0


def _load_plan(root: Path) -> tuple[dict, list[dict], Path, NcnnArtifacts, Path]:
    plan_path = root / "task-plan" / "real-pilot-task-plan.json"
    if not plan_path.is_file():
        raise ValueError("REAL_TASK_PLAN_REQUIRED")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    import base64
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(plan["public_key_b64"]))
    if not verify_document(plan, public):
        raise ValueError("REAL_TASK_PLAN_SIGNATURE_INVALID")
    for ref in plan.get("segments", []):
        bundle = json.loads((root / ref["bundle"]).read_text(encoding="utf-8"))
        if not verify_document(bundle, public):
            raise ValueError(f"TASK_BUNDLE_SIGNATURE_INVALID:{ref['task_id']}")
    source = root / plan["source_path"]
    if not source.is_file() or sha256(source) != plan["source_sha256"]:
        raise ValueError("SOURCE_HASH_MISMATCH")
    stage = root / "runtime" / "env-installer" / "realesrgan-stage-20260827T170159Z" / "realesrgan-ncnn-vulkan-v0.2.0-windows"
    canonical = root / "tools" / "realesrgan-ncnn-vulkan"
    candidates = [canonical, stage] if (canonical / "realesrgan-ncnn-vulkan.exe").is_file() else [stage]
    runtime = candidates[0]
    artifacts = NcnnArtifacts(runtime / "realesrgan-ncnn-vulkan.exe", runtime / "models/realesrgan-x4plus.param", runtime / "models/realesrgan-x4plus.bin", EXE_SHA256, KNOWN["realesrgan-x4plus.param"], KNOWN["realesrgan-x4plus.bin"])
    return plan, plan["segments"], source, artifacts, runtime / "models"


def _run_pilot(root: Path, seconds: int, resume: bool = False) -> int:
    if platform.system() != "Windows":
        return 3
    try:
        plan, refs, source, artifacts, model_dir = _load_plan(root)
        selected = refs[:2] if seconds == 10 else refs
        run_id = plan["run_id"]
        run_dir = root / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        completed = []
        for ref in selected:
            segment_dir = run_dir / ref["task_id"]
            segment_manifest = segment_dir / "segment_manifest.json"
            if resume and segment_manifest.is_file():
                completed.append(ref["task_id"])
                continue
            segment_dir.mkdir(parents=True, exist_ok=True)
            input_frames, output_frames = segment_dir / "input_frames", segment_dir / "output_frames"
            input_frames.mkdir(exist_ok=True); output_frames.mkdir(exist_ok=True)
            start, end = ref["start_frame"], ref["end_frame_exclusive"]
            extract = ["ffmpeg", "-y", "-i", str(source), "-vf", f"select=between(n\\,{start}\\,{end - 1}),setpts=N/(30000/1001*TB)", "-fps_mode", "vfr", str(input_frames / "frame_%08d.png")]
            cp = run(extract)
            (segment_dir / "extract_command.json").write_text(json.dumps(extract, indent=2) + "\n", encoding="utf-8")
            (segment_dir / "extract_stderr.log").write_text(cp.stderr, encoding="utf-8")
            if cp.returncode != 0: raise RuntimeError("FRAME_EXTRACT_FAILED")
            bundle = json.loads((root / ref["bundle"]).read_text(encoding="utf-8"))
            result = execute_realesrgan_ncnn(bundle, segment_dir / "attempt-A001", input_path=source, command_input_path=input_frames, artifacts=artifacts, model_dir=model_dir)
            encode_list = segment_dir / "frames.ffconcat"
            # The executor owns the attempt output directory. Keep the
            # encoder pointed at that directory instead of a separate,
            # never-populated sibling.
            output_files = sorted((segment_dir / "attempt-A001" / "output").glob("*.png"))
            if not output_files: raise RuntimeError("OUTPUT_NOT_FOUND")
            encode_list.write_text("ffconcat version 1.0\n" + "\n".join(f"file '{p.as_posix()}'" for p in output_files) + "\n", encoding="utf-8")
            mkv = segment_dir / "segment.ffv1.mkv"
            enc = run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(encode_list), "-c:v", "ffv1", "-level", "3", "-g", "1", str(mkv)])
            (segment_dir / "encode_stderr.log").write_text(enc.stderr, encoding="utf-8")
            if enc.returncode != 0: raise RuntimeError("FFV1_ENCODE_FAILED")
            segment_manifest.write_text(json.dumps({"task_id": ref["task_id"], "start_frame": start, "end_frame_exclusive": end, "input_frames": len(list(input_frames.glob("*.png"))), "output_frames": len(output_files), "ffv1": str(mkv), "worker_state": "READY_FOR_RETURN", "fixture_call_count": 0, "attempt": result}, indent=2) + "\n", encoding="utf-8")
            completed.append(ref["task_id"])
        report = {"run_id": run_id, "pilot_seconds": seconds, "segments_completed": completed, "fixture_call_count": 0, "backend": "ncnn_vulkan", "worker_state": "READY_FOR_RETURN"}
        (run_dir / "pilot_result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 4


def _collect_evidence(root: Path) -> int:
    try:
        plan, _, _, _, _ = _load_plan(root)
        run_dir = root / "runs" / plan["run_id"]
        if not run_dir.is_dir():
            raise ValueError("RUN_NOT_FOUND")
        output = root / "output"; output.mkdir(parents=True, exist_ok=True)
        zip_path = output / f"DTVS-WINDOWS-1MIN-EVIDENCE-{plan['run_id']}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for base in [root / "output", root / "task-plan", run_dir]:
                if not base.exists(): continue
                for path in sorted(base.rglob("*")):
                    if path.is_file() and path != zip_path and path.suffix.lower() != ".png":
                        archive.write(path, path.relative_to(root).as_posix())
        (zip_path.with_suffix(zip_path.suffix + ".sha256")).write_text(f"{sha256(zip_path)}  {zip_path.name}\n", encoding="ascii")
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 4


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
    if args.action == "run-10s": return _run_pilot(args.root, 10)
    if args.action == "run-1min": return _run_pilot(args.root, 60)
    if args.action == "resume-1min": return _run_pilot(args.root, 60, resume=True)
    if args.action == "collect-evidence": return _collect_evidence(args.root)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
