from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def ffprobe_json(path: Path, *, count_frames: bool = False) -> dict[str, Any]:
    cmd = ["ffprobe", "-v", "error", "-show_format", "-show_streams"]
    if count_frames:
        cmd.append("-count_frames")
    cmd += ["-of", "json", str(path)]
    cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return json.loads(cp.stdout)


def first_video_stream(probe: dict[str, Any]) -> dict[str, Any]:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    raise ValueError("SOURCE_VIDEO_STREAM_MISSING")


def has_audio_stream(probe: dict[str, Any]) -> bool:
    return any(stream.get("codec_type") == "audio" for stream in probe.get("streams", []))


def has_subtitle_stream(probe: dict[str, Any]) -> bool:
    return any(stream.get("codec_type") == "subtitle" for stream in probe.get("streams", []))

