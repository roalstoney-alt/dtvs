from __future__ import annotations

from pathlib import Path
from typing import Any


def write_pilot_report(path: Path, summary: dict[str, Any]) -> None:
    rows = [
        "# DTVS v0.2.2 Fixture Pilot Report",
        "",
        "## Measured Facts",
        "",
        f"- Run ID: {summary['run_id']}",
        f"- Fixture mode: {summary['fixture_mode']}",
        f"- Task count: {summary['task_count']}",
        f"- Accepted tasks: {summary['accepted_count']}",
        f"- Final state: {summary['final_state']}",
        "",
        "## Unverified Claims",
        "",
        "- RTX 4060 runtime: SKIPPED_WITH_REASON: no real RTX 4060 execution in this environment",
        "- Legal film source: SKIPPED_WITH_REASON: operator media not supplied",
        "- Model quality: SKIPPED_WITH_REASON: Real-ESRGAN model not executed",
        "- CENTRALIZED_COMPARISON_NOT_AVAILABLE",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

