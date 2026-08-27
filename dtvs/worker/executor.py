from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dtvs.common.hashing import sha256_bytes, sha256_file
from dtvs.worker.checkpoint import write_checkpoint
from dtvs.worker.energy import write_fixture_energy_sample


def execute_fixture(bundle: dict[str, Any], attempt_dir: Path, *, attempt_id: str, frame_count_delta: int = 0) -> dict[str, Any]:
    attempt_dir.mkdir(parents=True, exist_ok=True)
    expected = bundle["output"]["expected_core_frames"]
    actual = expected + frame_count_delta
    output = attempt_dir / "core_output.fixture"
    payload = {
        "task_id": bundle["task_id"],
        "attempt_id": attempt_id,
        "core": bundle["core"],
        "actual_core_frames": actual,
        "mock_restoration": True,
    }
    output.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    write_checkpoint(
        attempt_dir / "checkpoints.json",
        {"task_id": bundle["task_id"], "attempt_id": attempt_id, "completed_frames": max(0, actual), "checkpoint_valid": True},
    )
    write_fixture_energy_sample(attempt_dir / "energy.csv")
    output_hash = sha256_file(output)
    return {
        "schema_version": "0.2.2",
        "task_id": bundle["task_id"],
        "bundle_version": bundle["bundle_version"],
        "attempt_id": attempt_id,
        "state": "RUNNING",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "actual_command": ["dtvs-worker", "fixture-execute"],
        "output_path": str(output),
        "output_sha256": output_hash,
        "output_summary_hash": sha256_bytes(json.dumps(payload, sort_keys=True).encode()),
        "expected_core_frames": expected,
        "actual_core_frames": actual,
        "status_transitions": [],
        "mock_restoration": True,
    }

