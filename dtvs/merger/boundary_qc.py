from __future__ import annotations

from typing import Any


def check_boundaries(index: dict[str, Any], segment_start: int, segment_end: int) -> dict[str, Any]:
    entries = index["accepted"]
    cursor = segment_start
    gaps = []
    overlaps = []
    for entry in entries:
        core = entry["core"]
        if core["start_frame"] > cursor:
            gaps.append({"start_frame": cursor, "end_frame_exclusive": core["start_frame"]})
        if core["start_frame"] < cursor:
            overlaps.append(entry["task_id"])
        cursor = max(cursor, core["end_frame_exclusive"])
    if cursor < segment_end:
        gaps.append({"start_frame": cursor, "end_frame_exclusive": segment_end})
    return {"schema_version": "0.2.2", "gaps": gaps, "overlaps": overlaps, "ok": not gaps and not overlaps and index["complete"]}

