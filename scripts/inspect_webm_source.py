#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dtvs.common.hashing import sha256_file
from dtvs.common.media_probe import ffprobe_json, first_video_stream


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    args = ap.parse_args()
    source = Path(args.source)
    probe = ffprobe_json(source, count_frames=True)
    stream = first_video_stream(probe)
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:v:0", "-f", "null", "-"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(
        json.dumps(
            {
                "filename": source.name,
                "bytes": source.stat().st_size,
                "sha256": sha256_file(source),
                "codec": stream.get("codec_name"),
                "width": stream.get("width"),
                "height": stream.get("height"),
                "r_frame_rate": stream.get("r_frame_rate"),
                "avg_frame_rate": stream.get("avg_frame_rate"),
                "duration": float(probe["format"]["duration"]),
                "decode_ok": decode.returncode == 0,
                "decode_error_lines": len([line for line in decode.stderr.splitlines() if line.strip()]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if decode.returncode == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
