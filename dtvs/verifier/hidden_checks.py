from __future__ import annotations

from typing import Any


def evaluate_hidden_checks(task_id: str, hidden_summary: list[dict[str, Any]]) -> dict[str, Any]:
    entry = next((item for item in hidden_summary if item["task_id"] == task_id), None)
    if not entry:
        return {"ok": False, "reason": "CLOUD_HIDDEN_CHECK_FAILED"}
    return {"ok": True, "checked_commitments": entry["hidden_frame_commitments"]}


def deterministic_rerender_tasks(task_ids: list[str], count: int) -> list[str]:
    return sorted(task_ids)[:count]

