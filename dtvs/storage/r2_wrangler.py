from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Protocol

from dtvs.common.hashing import sha256_file


class Runner(Protocol):
    def run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        ...


class SubprocessRunner:
    def run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def wrangler_cmd(*args: str) -> list[str]:
    return ["npx", "wrangler", *args]


def upload_and_verify(manifest: dict[str, Any], run_root: Path, *, runner: Runner, resume: bool = False) -> dict[str, Any]:
    verify_dir = run_root / "upload-control" / "verify-temp"
    verify_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = run_root / "upload-control" / "upload_receipt.json"
    verified_existing = set()
    if resume and receipt_path.exists():
        existing = json.loads(receipt_path.read_text(encoding="utf-8"))
        verified_existing = {item["object_key"] for item in existing.get("objects", []) if item.get("verified")}
    objects = []
    for obj in manifest["objects"]:
        if obj["object_key"] in verified_existing:
            objects.append({**obj, "action": "SKIPPED_IDENTICAL", "downloaded_sha256": obj["sha256"], "verified": True, "attempts": 0})
            continue
        local = run_root / obj["local_path"]
        put = runner.run(wrangler_cmd("r2", "object", "put", f"{manifest['bucket']}/{obj['object_key']}", "--file", str(local), "--content-type", obj["content_type"]))
        if put.returncode != 0:
            objects.append({**obj, "action": "FAILED", "verified": False, "attempts": 1})
            continue
        downloaded = verify_dir / obj["sha256"]
        get = runner.run(wrangler_cmd("r2", "object", "get", f"{manifest['bucket']}/{obj['object_key']}", "--file", str(downloaded)))
        if get.returncode != 0 or not downloaded.exists():
            objects.append({**obj, "action": "FAILED_VERIFY_DOWNLOAD", "verified": False, "attempts": 1})
            continue
        downloaded_sha = sha256_file(downloaded)
        downloaded_bytes = downloaded.stat().st_size
        downloaded.unlink(missing_ok=True)
        verified = downloaded_sha == obj["sha256"] and downloaded_bytes == obj["bytes"]
        objects.append({**obj, "action": "UPLOADED", "downloaded_sha256": downloaded_sha, "verified": verified, "attempts": 1})
    summary = {
        "expected": len(manifest["objects"]),
        "uploaded": sum(1 for item in objects if item["action"] == "UPLOADED"),
        "skipped_identical": sum(1 for item in objects if item["action"] == "SKIPPED_IDENTICAL"),
        "failed": sum(1 for item in objects if not item["verified"]),
        "verified": sum(1 for item in objects if item["verified"]),
    }
    receipt = {
        "schema_version": "0.2.2",
        "run_id": manifest["run_id"],
        "bucket": manifest["bucket"],
        "state": "VERIFIED" if summary["verified"] == summary["expected"] else "PARTIAL",
        "objects": objects,
        "summary": summary,
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt

