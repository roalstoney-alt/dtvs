from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Fault:
    task_id: str
    type: str
    at_progress_pct: int | None = None


def load_faults(config: dict[str, Any]) -> dict[str, Fault]:
    faults = {}
    for item in config.get("fault_injection", {}).get("faults", []):
        faults[item["task_id"]] = Fault(item["task_id"], item["type"], item.get("at_progress_pct"))
    return faults

