from __future__ import annotations

from pathlib import Path
from typing import Any

from dtvs.common.hashing import sha256_file


def check_uploaded_attempt(attempt_dir: Path) -> dict[str, Any]:
    attempt = __import__("json").loads((attempt_dir / "attempt_manifest.json").read_text(encoding="utf-8"))
    local_qc = __import__("json").loads((attempt_dir / "local_qc.json").read_text(encoding="utf-8"))
    output = attempt_dir / "core_output.fixture"
    checks = {
        "evidence_manifest_present": (attempt_dir / "attempt_manifest.json").exists(),
        "local_qc_present": (attempt_dir / "local_qc.json").exists(),
        "worker_did_not_self_accept": local_qc.get("state") != "ACCEPTED",
        "output_present_when_allowed": (not local_qc["upload_allowed"]) or output.exists(),
        "output_hash_matches": (not output.exists()) or sha256_file(output) == attempt["output_sha256"],
        "frame_count_exact": attempt["actual_core_frames"] == attempt["expected_core_frames"],
    }
    return {"checks": checks, "ok": all(checks.values()), "attempt": attempt, "local_qc": local_qc}

