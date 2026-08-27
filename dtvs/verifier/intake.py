from __future__ import annotations

from pathlib import Path


def list_attempt_dirs(cloud_inbox: Path) -> list[Path]:
    if not cloud_inbox.exists():
        return []
    return sorted(path for path in cloud_inbox.glob("*/*") if path.is_dir() and not path.name.endswith(".staging"))

