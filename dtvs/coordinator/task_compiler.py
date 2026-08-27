from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dtvs.contracts.models import FrameRange, TaskBundle
from dtvs.contracts.signing import sign_document
from dtvs.contracts.validation import validate_document
from dtvs.coordinator.scene_splitter import assert_contiguous, split_fixed, with_context
from dtvs.coordinator.verification_points import hidden_check_summary, public_anchor


def compile_tasks(
    asset: dict[str, Any],
    config: dict[str, Any],
    *,
    private_key: Ed25519PrivateKey,
    key_id: str,
    output_dir: Path,
    hidden_secret: bytes,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    core_ranges = split_fixed(asset, config)
    assert_contiguous(core_ranges, asset["segment_start_frame"], asset["segment_end_frame_exclusive"])
    task_index = []
    hidden = []
    expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    for idx, core in enumerate(core_ranges, start=1):
        task_id = f"DTVS-P001-T{idx:04d}"
        context = with_context(core, asset, config["context_frames"])
        anchor = public_anchor(task_id, core)
        bundle = TaskBundle(
            task_id=task_id,
            bundle_version=1,
            asset_id=asset["asset_id"],
            core=FrameRange(**core),
            context=FrameRange(**context),
            input={"path_or_object_key": config["source_path"], "sha256": asset["source_sha256"], "public_anchor": anchor},
            execution={
                "worker_pack_version": config["worker_pack_version"],
                "pipeline_id": config["pipeline_id"],
                "model_sha256": config["model_sha256"],
                "parameters_sha256": config["parameters_sha256"],
                "random_seed": config["random_seed"],
            },
            output={
                "width": config["output_width"],
                "height": config["output_height"],
                "fps_num": config["fps_num"],
                "fps_den": config["fps_den"],
                "pixel_format": config["pixel_format"],
                "expected_core_frames": core["end_frame_exclusive"] - core["start_frame"],
            },
            lease={"expires_at": expires_at, "checkpoint_frames": config["checkpoint_frames"]},
            verification={"upload_threshold": config["upload_threshold"], "minimum_component_score": config["minimum_component_score"]},
        )
        signed = sign_document(bundle.to_dict(), private_key, key_id)
        validate_document(signed, Path("schemas/task_bundle_v022.schema.json"))
        bundle_path = output_dir / f"{task_id}.bundle.json"
        bundle_path.write_text(json.dumps(signed, indent=2, ensure_ascii=False), encoding="utf-8")
        task_index.append({"task_id": task_id, "bundle_path": str(bundle_path), "core": core, "context": context, "state": "CREATED"})
        hidden.append(hidden_check_summary(task_id, core, hidden_secret, count=1))
    return {"tasks": task_index, "hidden_check_summary": hidden, "split_reason": "FALLBACK_FIXED_FRAME_SPLIT"}

