from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path


def write_fixture_energy_sample(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if new:
            writer.writerow(["timestamp_utc", "source", "power_w", "note"])
        writer.writerow([datetime.now(timezone.utc).isoformat(), "fixture", "0", "SKIPPED_WITH_REASON: no RTX 4060 measurement"])

