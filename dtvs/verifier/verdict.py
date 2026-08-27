from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dtvs.common.canonical_json import dumps
from dtvs.common.hashing import sha256_bytes
from dtvs.verifier.hidden_checks import evaluate_hidden_checks
from dtvs.verifier.structural_qc import check_uploaded_attempt


def make_verdict(attempt_dir: Path, hidden_summary: list[dict[str, Any]], rerender_selected: bool = False) -> dict[str, Any]:
    structural = check_uploaded_attempt(attempt_dir)
    task_id = structural["attempt"]["task_id"]
    hidden = evaluate_hidden_checks(task_id, hidden_summary)
    verdict = "ACCEPTED" if structural["ok"] and hidden["ok"] and structural["local_qc"]["upload_allowed"] else "REJECTED"
    reason_codes = []
    if not structural["ok"]:
        reason_codes.append("EVIDENCE_INCOMPLETE")
    if not hidden["ok"]:
        reason_codes.append("CLOUD_HIDDEN_CHECK_FAILED")
    if not structural["local_qc"]["upload_allowed"]:
        reason_codes.extend(structural["local_qc"].get("reason_codes", []))
    doc = {
        "schema_version": "0.2.2",
        "task_id": task_id,
        "attempt_id": structural["attempt"]["attempt_id"],
        "verifier_version": "0.1.0-fixture",
        "structural_qc": structural["checks"],
        "hidden_checks": hidden,
        "center_rerender_selected": rerender_selected,
        "verdict": verdict,
        "reason_codes": sorted(set(reason_codes)),
    }
    doc["verdict_hash"] = sha256_bytes(dumps(doc))
    (attempt_dir / "cloud_verdict.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc

