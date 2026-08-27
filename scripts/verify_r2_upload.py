#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()
    receipt = Path(args.manifest).with_name("upload_receipt.json")
    if not receipt.exists():
        print(json.dumps({"state": "RECEIPT_MISSING"}, indent=2))
        return 6
    data = json.loads(receipt.read_text(encoding="utf-8"))
    print(json.dumps({"state": data["state"], "summary": data["summary"]}, indent=2))
    return 0 if data["state"] == "VERIFIED" else 7


if __name__ == "__main__":
    raise SystemExit(main())

