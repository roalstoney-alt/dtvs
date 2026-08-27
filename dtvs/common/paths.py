from __future__ import annotations

from pathlib import Path


def ensure_inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    base = root.resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"path escapes root: {path}")
    return resolved

