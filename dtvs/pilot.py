from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dtvs.coordinator.asset_freezer import freeze_asset
from dtvs.coordinator.task_compiler import compile_tasks
from dtvs.contracts.signing import generate_private_key, public_key_bytes
from dtvs.faults import load_faults
from dtvs.merger.accepted_index import build_accepted_index
from dtvs.merger.video_merge import merge_fixture
from dtvs.reporting.economics import fixture_cost_summary
from dtvs.reporting.evidence_manifest import write_json
from dtvs.reporting.pilot_report import write_pilot_report
from dtvs.verifier.hidden_checks import deterministic_rerender_tasks
from dtvs.verifier.intake import list_attempt_dirs
from dtvs.verifier.verdict import make_verdict
from dtvs.worker.executor import execute_fixture
from dtvs.worker.local_qc import local_qc
from dtvs.worker.preflight import preflight_bundle
from dtvs.worker.uploader import upload_attempt


def run_fixture_pilot(config_path: Path, output_root: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not config.get("fixture_mode"):
        raise RuntimeError("Real RTX 4060 pilot must be run by an operator with legal media and model files")
    run_id = config["run_id"]
    run_dir = output_root / run_id
    if config.get("fixture_mode") and run_dir.exists():
        shutil.rmtree(run_dir)
    coordinator_dir = run_dir / "coordinator"
    worker_dir = run_dir / "worker"
    cloud = run_dir / "simulated_cloud" / "inbox"
    merge_dir = run_dir / "merge"
    private_key = generate_private_key()
    public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes(private_key))
    asset = freeze_asset(config, Path.cwd())
    compiled = compile_tasks(asset, config, private_key=private_key, key_id="pilot-local-001", output_dir=coordinator_dir / "bundles", hidden_secret=b"fixture-hidden")
    write_json(coordinator_dir / "asset_manifest.json", asset)
    write_json(coordinator_dir / "task_index.json", compiled["tasks"])
    write_json(coordinator_dir / "hidden_check_summary.json", compiled["hidden_check_summary"])
    faults = load_faults(config)
    recovery_records = []
    accepted_seen: set[str] = set()
    rerender = set(deterministic_rerender_tasks([task["task_id"] for task in compiled["tasks"]], config["rerender_task_count"]))

    for task in compiled["tasks"]:
        task_id = task["task_id"]
        bundle = json.loads(Path(task["bundle_path"]).read_text(encoding="utf-8"))
        fault = faults.get(task_id)
        attempts = 1
        while True:
            if task_id in accepted_seen:
                recovery_records.append({"task_id": task_id, "action": "SKIP_ALREADY_ACCEPTED", "final_state": "ACCEPTED"})
                break
            attempt_id = f"A{attempts:03d}"
            attempt_dir = worker_dir / task_id / attempt_id
            preflight = preflight_bundle(bundle, public_key, attempt_dir, fixture_mode=True)
            if not preflight["ok"]:
                raise RuntimeError("fixture preflight failed")
            frame_delta = -1 if fault and fault.type == "FRAME_COUNT_ERROR" and attempts == 1 else 0
            attempt = execute_fixture(bundle, attempt_dir, attempt_id=attempt_id, frame_count_delta=frame_delta)
            force_low = bool(fault and fault.type == "FORCE_LOCAL_SCORE_BELOW_THRESHOLD" and attempts == 1)
            qc = local_qc(bundle, attempt, force_low_score=force_low)
            detected_by = "worker"
            recovery_action = "NONE"
            active_fault = fault if attempts == 1 else None
            if active_fault:
                if active_fault.type == "PROCESS_TERMINATION":
                    recovery_action = "RESUME_FROM_CHECKPOINT"
                    attempt["recomputed_frames"] = bundle["lease"]["checkpoint_frames"]
                elif active_fault.type == "UPLOAD_INTERRUPTION":
                    recovery_action = "IDEMPOTENT_UPLOAD_RETRY"
                    upload_attempt(attempt, qc, cloud)
                elif active_fault.type == "OUTPUT_HASH_MISMATCH":
                    attempt["output_sha256"] = "0" * 64
                    detected_by = "uploader"
                    recovery_action = "REASSIGN_AFTER_BAD_HASH"
                elif active_fault.type == "FORCE_LOCAL_SCORE_BELOW_THRESHOLD":
                    recovery_action = "REASSIGN_AFTER_LOCAL_REJECT"
                elif active_fault.type == "FRAME_COUNT_ERROR":
                    recovery_action = "REASSIGN_AFTER_FRAME_COUNT_ERROR"
            try:
                upload_attempt(attempt, qc, cloud)
                verdict = make_verdict(cloud / task_id / attempt_id, compiled["hidden_check_summary"], rerender_selected=task_id in rerender)
            except ValueError:
                verdict = {"verdict": "REJECTED", "reason_codes": ["OUTPUT_HASH_MISMATCH"]}
            final_state = verdict["verdict"]
            recovery_records.append(
                {
                    "task_id": task_id,
                    "expected_fault": active_fault.type if active_fault else None,
                    "actual_trigger": active_fault.at_progress_pct if active_fault else None,
                    "detected_by": detected_by,
                    "recovery_action": recovery_action,
                    "recovery_time_seconds": 0,
                    "recomputed_frames": attempt.get("recomputed_frames", 0),
                    "attempt_id": attempt_id,
                    "final_state": final_state,
                }
            )
            if final_state == "ACCEPTED":
                accepted_seen.add(task_id)
                break
            attempts += 1
            if attempts > 2:
                break

    attempt_dirs = list_attempt_dirs(cloud)
    index = build_accepted_index(attempt_dirs, compiled["tasks"])
    delivery = merge_fixture(index, merge_dir, segment_start=config["segment_start_frame"], segment_end=config["segment_end_frame_exclusive"])
    accepted_count = len(index["accepted"])
    summary = {
        "schema_version": "0.2.2",
        "run_id": run_id,
        "fixture_mode": True,
        "task_count": len(compiled["tasks"]),
        "accepted_count": accepted_count,
        "final_state": "PARTIAL" if accepted_count != len(compiled["tasks"]) else delivery["state"],
        "delivery": delivery,
        "cost": fixture_cost_summary(),
    }
    write_json(run_dir / "fault_injection_report.json", recovery_records)
    write_json(run_dir / "pilot_summary.json", summary)
    write_pilot_report(run_dir / "pilot_summary.md", summary)
    return summary
