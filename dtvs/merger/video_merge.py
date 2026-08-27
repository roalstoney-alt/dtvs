from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dtvs.common.hashing import sha256_file
from dtvs.merger.boundary_qc import check_boundaries


def merge_fixture(index: dict[str, Any], output_dir: Path, *, segment_start: int, segment_end: int) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    boundary = check_boundaries(index, segment_start, segment_end)
    name = "final_output.fixture" if boundary["ok"] else "INCOMPLETE_DIAGNOSTIC_ONLY.fixture"
    final = output_dir / name
    final.write_text(json.dumps({"accepted": index["accepted"], "boundary_qc": boundary}, sort_keys=True), encoding="utf-8")
    result = {
        "schema_version": "0.2.2",
        "state": "COMPLETE" if boundary["ok"] else "INCOMPLETE_DIAGNOSTIC_ONLY",
        "final_path": str(final),
        "final_sha256": sha256_file(final),
        "boundary_qc": boundary,
        "audio_subtitle_status": "CENTER_FIXTURE_PLACEHOLDER",
    }
    (output_dir / "delivery.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result

