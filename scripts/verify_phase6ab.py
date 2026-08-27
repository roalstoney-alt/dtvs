#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    run = Path("runs") / args.run_id
    required = [run / "run_manifest.json", run / "center" / "master" / "asset_manifest.json", run / "center" / "task_index.json", run / "upload-control" / "upload_manifest.json"]
    missing = [str(path) for path in required if not path.exists()]
    print(json.dumps({"run_id": args.run_id, "phase6a": "PASS" if not missing else "FAIL", "missing": missing}, indent=2))
    return 0 if not missing else 8


if __name__ == "__main__":
    raise SystemExit(main())

