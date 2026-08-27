from __future__ import annotations

from typing import Any


def split_fixed(asset: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    start = asset["segment_start_frame"]
    end = asset["segment_end_frame_exclusive"]
    fps_num = config["fps_num"]
    fps_den = config["fps_den"]
    frames_per_task = config["target_task_seconds"] * fps_num // fps_den
    ranges = []
    cursor = start
    while cursor < end:
        nxt = min(cursor + frames_per_task, end)
        ranges.append({"start_frame": cursor, "end_frame_exclusive": nxt})
        cursor = nxt
    return ranges


def with_context(core: dict[str, int], asset: dict[str, Any], context_frames: int) -> dict[str, int]:
    return {
        "start_frame": max(asset["segment_start_frame"], core["start_frame"] - context_frames),
        "end_frame_exclusive": min(asset["segment_end_frame_exclusive"], core["end_frame_exclusive"] + context_frames),
    }


def assert_contiguous(ranges: list[dict[str, int]], start: int, end: int) -> None:
    if not ranges:
        raise ValueError("no ranges")
    if ranges[0]["start_frame"] != start:
        raise ValueError("first range does not start at segment start")
    cursor = start
    for item in ranges:
        if item["start_frame"] != cursor:
            raise ValueError("gap or overlap detected")
        if item["end_frame_exclusive"] <= item["start_frame"]:
            raise ValueError("empty range")
        cursor = item["end_frame_exclusive"]
    if cursor != end:
        raise ValueError("last range does not end at segment end")

