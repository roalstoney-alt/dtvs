from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dtvs.common.hashing import sha256_file
from dtvs.common.paths import ensure_inside
from dtvs.storage.upload_policy import classify_allowed, validate_run_id


CONTENT_TYPES = {
    ".mkv": "video/x-matroska",
    ".json": "application/json",
    ".sig": "application/octet-stream",
}


def build_upload_manifest(config: dict[str, Any]) -> dict[str, Any]:
    run_id = config["run_id"]
    validate_run_id(run_id)
    run_root = Path(config["local_run_root"]).resolve()
    remote_prefix = config["remote_prefix"].rstrip("/")
    limit = config["wrangler_single_object_limit_bytes"]
    task_index = json.loads((run_root / "center" / "task_index.json").read_text(encoding="utf-8"))
    tasks = task_index["tasks"] if isinstance(task_index, dict) else task_index
    objects = []
    seen_keys = set()
    ordered = []
    for task in tasks:
        short = task["task_id"].split("-")[-1].replace("T", "T")
        task_dir = run_root / "task-inputs" / short
        for filename in ["input_with_context.mkv", "public_anchors.json", "task_bundle.json", "task_bundle.sig"]:
            ordered.append((task["task_id"], task_dir / filename))
    ordered += [
        (None, run_root / "public" / "task_index.json"),
        (None, run_root / "public" / "run_manifest.json"),
    ]
    for task_id, local in ordered:
        resolved = ensure_inside(local, run_root)
        if not resolved.exists():
            raise FileNotFoundError(local)
        classification = classify_allowed(resolved, limit, config.get("forbidden_name_patterns"))
        rel = resolved.relative_to(run_root).as_posix()
        object_key = f"{remote_prefix}/{rel}"
        if object_key in seen_keys:
            raise ValueError("duplicate object key")
        seen_keys.add(object_key)
        objects.append(
            {
                "local_path": rel,
                "object_key": object_key,
                "bytes": resolved.stat().st_size,
                "sha256": sha256_file(resolved),
                "content_type": CONTENT_TYPES[resolved.suffix.lower()],
                "task_id": task_id,
                "classification": classification,
            }
        )
    return {
        "schema_version": "0.2.2",
        "run_id": run_id,
        "bucket": config["bucket"],
        "remote_prefix": remote_prefix,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "objects": objects,
        "totals": {
            "objects": len(objects),
            "bytes": sum(item["bytes"] for item in objects),
            "tasks": len(tasks),
        },
    }
