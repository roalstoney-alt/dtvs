#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dtvs.storage.r2_wrangler import SubprocessRunner, upload_and_verify


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    if not os.environ.get("CLOUDFLARE_ACCOUNT_ID") or not os.environ.get("CLOUDFLARE_API_TOKEN"):
        print(json.dumps({"state": "BLOCKED_CREDENTIALS_MISSING", "CLOUDFLARE_ACCOUNT_ID": "present" if os.environ.get("CLOUDFLARE_ACCOUNT_ID") else "missing", "CLOUDFLARE_API_TOKEN": "present" if os.environ.get("CLOUDFLARE_API_TOKEN") else "missing"}, indent=2))
        return 4
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = upload_and_verify(manifest, manifest_path.parents[1], runner=SubprocessRunner(), resume=args.resume)
    print(json.dumps({"receipt": str(manifest_path.parents[1] / "upload-control" / "upload_receipt.json"), "state": receipt["state"]}, indent=2))
    return 0 if receipt["state"] == "VERIFIED" else 5


if __name__ == "__main__":
    raise SystemExit(main())
