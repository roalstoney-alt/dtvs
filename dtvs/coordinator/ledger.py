from __future__ import annotations

import json
from pathlib import Path

from dtvs.contracts.state_machine import transition


def write_event(events_path: Path, event: dict) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def create_task(events_path: Path, task_id: str) -> dict:
    ev = transition("CREATED", "LEASED", actor="coordinator", reason_code="TASK_COMPILED", evidence={"task_id": task_id})
    data = ev.to_dict()
    write_event(events_path, data)
    return data

