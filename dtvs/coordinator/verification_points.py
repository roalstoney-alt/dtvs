from __future__ import annotations

import hmac
from typing import Any

from dtvs.common.hashing import sha256_bytes


def public_anchor(task_id: str, core: dict[str, int]) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "anchor_hash": sha256_bytes(f"{task_id}:{core['start_frame']}:{core['end_frame_exclusive']}".encode()),
        "core_start_frame": core["start_frame"],
        "core_end_frame_exclusive": core["end_frame_exclusive"],
    }


def hidden_check_summary(task_id: str, core: dict[str, int], secret: bytes, count: int = 1) -> dict[str, Any]:
    span = core["end_frame_exclusive"] - core["start_frame"]
    positions = []
    for idx in range(count):
        digest = hmac.digest(secret, f"{task_id}:{idx}".encode(), "sha256")
        offset = int.from_bytes(digest[:8], "big") % span
        frame = core["start_frame"] + offset
        positions.append({"ordinal": idx, "frame_commitment": sha256_bytes(f"{task_id}:{frame}".encode())})
    return {"task_id": task_id, "hidden_frame_commitments": positions}

