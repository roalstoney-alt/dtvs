#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dtvs.storage.r2_manifest import build_upload_manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--bucket", default="dtvs-pilot-assets")
    args = ap.parse_args()
    run_root = Path("runs") / args.run_id
    config = {
        "schema_version": "0.2.2",
        "bucket": args.bucket,
        "run_id": args.run_id,
        "local_run_root": str(run_root),
        "remote_prefix": f"runs/{args.run_id}",
        "wrangler_single_object_limit_bytes": 330301440,
        "overwrite_existing": False,
        "allowed_suffixes": [".mkv", ".json", ".sig"],
        "forbidden_name_patterns": ["source_master", "source_20m_video", "source_20m_audio", "subtitles_20m", "hidden_check", "private_key", ".pem", ".key"],
    }
    manifest = build_upload_manifest(config)
    out = run_root / "upload-control" / "upload_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(out), "objects": manifest["totals"]["objects"], "bytes": manifest["totals"]["bytes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
