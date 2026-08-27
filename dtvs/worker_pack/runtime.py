from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dtvs.common.hashing import sha256_file
from dtvs.worker.executor import execute_fixture
from dtvs.worker.local_qc import local_qc
from dtvs.worker_pack import WORKER_PACK_VERSION
from dtvs.worker_pack.package import ImportedTask, import_handoff_tasks, import_task_package


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_event(workspace: Path, event: str, **fields: Any) -> None:
    events = workspace / "worker_events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    with events.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"timestamp_utc": utc(), "event": event, **fields}, ensure_ascii=False) + "\n")


def doctor(workspace: Path | None = None, *, require_model: bool = False) -> dict[str, Any]:
    workspace = workspace or Path.cwd()
    model_dir = workspace / "models"
    checks = {
        "python_3_11_or_newer": tuple(platform.python_version_tuple()) >= ("3", "11", "0"),
        "ffmpeg_present": bool(shutil.which("ffmpeg")),
        "ffprobe_present": bool(shutil.which("ffprobe")),
        "workspace_writable": True,
        "model_present": model_dir.exists() if require_model else True,
    }
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        probe = workspace / ".dtvs_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        checks["workspace_writable"] = False
    gpu = subprocess.run(["nvidia-smi"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False) if shutil.which("nvidia-smi") else None
    result = {
        "schema_version": "0.2.2",
        "worker_pack_version": WORKER_PACK_VERSION,
        "checked_at": utc(),
        "checks": checks,
        "gpu_status": "PRESENT" if gpu and gpu.returncode == 0 else "SKIPPED_WITH_REASON: nvidia-smi unavailable",
        "power_gate": "SKIPPED_WITH_REASON: power is logged but not an acceptance gate in v0.1.0",
        "ok": all(checks.values()),
    }
    if workspace:
        write_event(workspace, "DOCTOR", ok=result["ok"])
    return result


def _attempt_dir(workspace: Path, run_id: str, task_id: str) -> Path:
    return workspace / "runs" / run_id / "tasks" / task_id


def _run_imported_task(imported: ImportedTask, workspace: Path, *, force_low_score: bool = False, simulate_interrupt: bool = False) -> dict[str, Any]:
    bundle = imported.bundle
    run_id = imported.run_id or bundle.get("run_id") or bundle["task_id"].rsplit("-", 1)[0]
    task_dir = _attempt_dir(workspace, run_id, bundle["task_id"])
    attempt_dir = task_dir / "attempt-A001"
    manifest_path = attempt_dir / "attempt_manifest.json"
    output_path = attempt_dir / "core_output.fixture"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("worker_state") == "READY_FOR_RETURN" and output_path.exists() and sha256_file(output_path) == manifest.get("output_sha256"):
            write_event(workspace, "TASK_SKIPPED_COMPLETED", task_id=bundle["task_id"], run_id=run_id)
            return {**manifest, "action": "SKIPPED_COMPLETED"}
    checkpoint = attempt_dir / "checkpoints.json"
    if simulate_interrupt and not checkpoint.exists():
        attempt_dir.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(json.dumps({"task_id": bundle["task_id"], "interrupted": True, "completed_frames": 120}), encoding="utf-8")
        write_event(workspace, "TASK_INTERRUPTED", task_id=bundle["task_id"], run_id=run_id)
        return {"schema_version": "0.2.2", "run_id": run_id, "task_id": bundle["task_id"], "worker_state": "INTERRUPTED", "ready_for_return": False}
    resumed = checkpoint.exists() and not manifest_path.exists()
    if resumed:
        write_event(workspace, "TASK_RESUMED", task_id=bundle["task_id"], run_id=run_id)
    attempt = execute_fixture(bundle, attempt_dir, attempt_id="A001")
    qc = local_qc(bundle, attempt, force_low_score=force_low_score)
    return_qc = dict(qc)
    return_qc.pop("state", None)
    worker_state = "READY_FOR_RETURN"
    manifest = {
        **attempt,
        "run_id": run_id,
        "worker_pack_version": WORKER_PACK_VERSION,
        "worker_state": worker_state,
        "ready_for_return": True,
        "resumed": resumed,
        "local_qc": return_qc,
        "highest_worker_state": "READY_FOR_RETURN",
    }
    serialized = json.dumps(manifest, ensure_ascii=False)
    if "ACCEPTED" in serialized:
        raise RuntimeError("WORKER_STATE_FORBIDDEN")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_event(workspace, "TASK_READY_FOR_RETURN", task_id=bundle["task_id"], run_id=run_id, upload_allowed=return_qc["upload_allowed"])
    return manifest


def run_task(package_path: Path, workspace: Path, *, force_low_score: bool = False, simulate_interrupt: bool = False) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    if package_path.is_dir():
        assignment, tasks = import_handoff_tasks(package_path)
        results = []
        for imported in tasks:
            results.append(_run_imported_task(imported, workspace, force_low_score=force_low_score, simulate_interrupt=False))
        ready = sum(1 for item in results if item.get("ready_for_return"))
        local_rejected = sum(1 for item in results if not item.get("local_qc", {}).get("upload_allowed", False))
        summary = {
            "schema_version": "0.2.2",
            "run_id": assignment["run_id"],
            "worker_pack_version": WORKER_PACK_VERSION,
            "worker_state": "READY_FOR_RETURN",
            "ready_for_return": ready,
            "local_rejected": local_rejected,
            "task_count": len(results),
            "results": results,
            "highest_worker_state": "READY_FOR_RETURN",
        }
        if "ACCEPTED" in json.dumps(summary, ensure_ascii=False):
            raise RuntimeError("WORKER_STATE_FORBIDDEN")
        (workspace / "runs" / assignment["run_id"] / "worker_run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        write_event(workspace, "HANDOFF_READY_FOR_RETURN", run_id=assignment["run_id"], ready_for_return=ready, local_rejected=local_rejected)
        return summary
    imported = import_task_package(package_path, workspace)
    return _run_imported_task(imported, workspace, force_low_score=force_low_score, simulate_interrupt=simulate_interrupt)


def export_run(workspace: Path, run_id: str, destination: Path) -> dict[str, Any]:
    run_dir = workspace / "runs" / run_id
    if not run_dir.exists():
        raise FileNotFoundError(run_dir)
    destination.mkdir(parents=True, exist_ok=True)
    zip_path = destination / f"{run_id}-worker-return.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(run_dir).as_posix())
    digest = sha256_file(zip_path)
    (zip_path.with_suffix(zip_path.suffix + ".sha256")).write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    write_event(workspace, "RUN_EXPORTED", run_id=run_id, destination=str(zip_path))
    return {"schema_version": "0.2.2", "run_id": run_id, "zip_path": str(zip_path), "sha256": digest}


def submit_run(workspace: Path, run_id: str, assignment: Path) -> dict[str, Any]:
    data = json.loads(assignment.read_text(encoding="utf-8")) if assignment.exists() else {}
    target = data.get("submit_url") or data.get("return_endpoint")
    if not target:
        offline_dir = workspace / "offline_returns"
        exported = export_run(workspace, run_id, offline_dir)
        write_event(workspace, "SUBMIT_DOWNGRADED_TO_OFFLINE_EXPORT", run_id=run_id)
        return {"schema_version": "0.2.2", "run_id": run_id, "state": "OFFLINE_RETURN_READY", "reason": "NETWORK_TARGET_NOT_CONFIGURED", "export": exported}
    return {"schema_version": "0.2.2", "run_id": run_id, "state": "NETWORK_SUBMIT_NOT_IMPLEMENTED", "reason": "v0.1.0 package does not create Cloudflare dependencies"}
