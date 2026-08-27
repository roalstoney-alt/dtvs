from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_accepted_index(attempt_dirs: list[Path], expected_tasks: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = {}
    for attempt_dir in attempt_dirs:
        verdict_path = attempt_dir / "cloud_verdict.json"
        if not verdict_path.exists():
            continue
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        if verdict["verdict"] == "ACCEPTED":
            if verdict["task_id"] in accepted:
                raise ValueError("DUPLICATE_ACCEPTED_RESULT")
            accepted[verdict["task_id"]] = {"attempt_dir": str(attempt_dir), "verdict": verdict}
    entries = []
    missing = []
    for task in sorted(expected_tasks, key=lambda item: item["core"]["start_frame"]):
        if task["task_id"] not in accepted:
            missing.append(task["task_id"])
            continue
        entries.append({"task_id": task["task_id"], "core": task["core"], "attempt_dir": accepted[task["task_id"]]["attempt_dir"]})
    return {"schema_version": "0.2.2", "accepted": entries, "missing_or_not_accepted": missing, "complete": not missing}

