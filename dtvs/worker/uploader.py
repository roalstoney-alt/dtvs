from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from dtvs.common.hashing import sha256_file


def upload_attempt(attempt: dict[str, Any], local_qc: dict[str, Any], cloud_inbox: Path) -> dict[str, Any]:
    task_dir = cloud_inbox / attempt["task_id"] / attempt["attempt_id"]
    staging = task_dir.with_name(task_dir.name + ".staging")
    staging.mkdir(parents=True, exist_ok=True)
    if local_qc["upload_allowed"]:
        src = Path(attempt["output_path"])
        dst_partial = staging / "core_output.fixture.partial"
        shutil.copyfile(src, dst_partial)
        dst = staging / "core_output.fixture"
        os.replace(dst_partial, dst)
        if sha256_file(dst) != attempt["output_sha256"]:
            raise ValueError("OUTPUT_HASH_MISMATCH")
    else:
        (staging / "failure_report.json").write_text(json.dumps(local_qc, ensure_ascii=False, indent=2), encoding="utf-8")
    (staging / "attempt_manifest.json").write_text(json.dumps(attempt, ensure_ascii=False, indent=2), encoding="utf-8")
    (staging / "local_qc.json").write_text(json.dumps(local_qc, ensure_ascii=False, indent=2), encoding="utf-8")
    if task_dir.exists():
        shutil.rmtree(task_dir)
    os.replace(staging, task_dir)
    return {"uploaded_to": str(task_dir), "video_uploaded": bool(local_qc["upload_allowed"])}

