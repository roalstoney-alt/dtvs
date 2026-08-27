from __future__ import annotations

from pathlib import Path
from typing import Any

from dtvs.common.hashing import sha256_bytes, sha256_file, sha256_uri


def freeze_asset(config: dict[str, Any], root: Path) -> dict[str, Any]:
    source = root / config["source_path"]
    if source.exists():
        digest = sha256_file(source)
        source_bytes = source.stat().st_size
    elif config.get("fixture_mode"):
        digest = sha256_bytes(f"fixture:{config['run_id']}:{config['segment_end_frame_exclusive']}".encode())
        source_bytes = 0
    else:
        raise FileNotFoundError(source)
    return {
        "schema_version": "0.2.2",
        "asset_id": sha256_uri(digest),
        "source_sha256": digest,
        "source_bytes": source_bytes,
        "video_stream_index": 0,
        "fps_num": config["fps_num"],
        "fps_den": config["fps_den"],
        "time_base_num": 1,
        "time_base_den": config["fps_num"],
        "width": config.get("source_width", 1920),
        "height": config.get("source_height", 1080),
        "total_frames": config["segment_end_frame_exclusive"],
        "segment_start_frame": config["segment_start_frame"],
        "segment_end_frame_exclusive": config["segment_end_frame_exclusive"],
        "rights_record": config["rights_record"],
        "fixture_mode": bool(config.get("fixture_mode")),
    }

