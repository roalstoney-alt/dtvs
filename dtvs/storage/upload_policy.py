from __future__ import annotations

import re
from pathlib import Path

FORBIDDEN_PATTERNS = [
    "source_master",
    "source_20m_video",
    "source_20m_audio",
    "subtitles_20m",
    "hidden_check",
    "private_key",
    ".pem",
    ".key",
]


def validate_run_id(run_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("unsafe run_id")


def classify_allowed(path: Path, limit_bytes: int, forbidden_patterns: list[str] | None = None) -> str:
    name = path.as_posix()
    patterns = forbidden_patterns or FORBIDDEN_PATTERNS
    lowered = name.lower()
    if any(pattern.lower() in lowered for pattern in patterns):
        raise ValueError(f"forbidden upload path: {path}")
    if path.is_symlink():
        raise ValueError(f"symlink not allowed: {path}")
    if path.stat().st_size > limit_bytes:
        raise ValueError("BLOCKED_OBJECT_TOO_LARGE_FOR_WRANGLER")
    suffix = path.suffix.lower()
    if suffix == ".mkv":
        return "WORKER_DISTRIBUTABLE"
    if suffix in {".json", ".sig"}:
        return "WORKER_METADATA"
    raise ValueError(f"suffix not allowed: {path}")

