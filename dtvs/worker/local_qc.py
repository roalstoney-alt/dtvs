from __future__ import annotations

from typing import Any


WEIGHTS = {
    "structure_anchor": 25,
    "temporal_consistency": 25,
    "artifact_hallucination": 20,
    "luma_color": 15,
    "boundary_continuity": 15,
}


def compute_las(components: dict[str, int]) -> dict[str, Any]:
    missing = set(WEIGHTS) - set(components)
    if missing:
        return {
            "algorithm_version": "LAS-v0.1-fixture",
            "human_review_required": True,
            "reason": "HUMAN_REVIEW_REQUIRED: missing component algorithms",
            "components": components,
            "score": None,
        }
    total = sum(components[name] * weight for name, weight in WEIGHTS.items()) / 100
    return {
        "algorithm_version": "LAS-v0.1-fixture",
        "human_review_required": False,
        "raw_features": {"fixture_components": components},
        "normalization": "identity_fixture_scores",
        "components": components,
        "score": total,
    }


def local_qc(bundle: dict[str, Any], attempt: dict[str, Any], *, force_low_score: bool = False) -> dict[str, Any]:
    hard_gates = {
        "bundle_signature_valid": True,
        "input_hash_matches": True,
        "model_hash_matches": True,
        "parameters_hash_matches": True,
        "output_decodable": True,
        "resolution_correct": True,
        "fps_timebase_correct": True,
        "pixel_format_correct": True,
        "core_frame_count_exact": attempt["actual_core_frames"] == bundle["output"]["expected_core_frames"],
        "no_missing_duplicate_black_frames": attempt["actual_core_frames"] == bundle["output"]["expected_core_frames"],
        "first_last_frame_mapping_correct": True,
        "output_and_evidence_sha256_present": bool(attempt.get("output_sha256")),
        "evidence_fields_complete": True,
    }
    if not all(hard_gates.values()):
        return {
            "schema_version": "0.2.2",
            "task_id": bundle["task_id"],
            "hard_gates": hard_gates,
            "las": None,
            "upload_allowed": False,
            "state": "LOCAL_REJECTED",
            "reason_codes": ["OUTPUT_STRUCTURE_INVALID"],
        }
    score = 65 if force_low_score else 92
    components = {name: score for name in WEIGHTS}
    las = compute_las(components)
    upload_allowed = las["score"] >= bundle["verification"]["upload_threshold"] and min(components.values()) >= bundle["verification"]["minimum_component_score"]
    return {
        "schema_version": "0.2.2",
        "task_id": bundle["task_id"],
        "hard_gates": hard_gates,
        "las": las,
        "upload_allowed": upload_allowed,
        "state": "UPLOADED" if upload_allowed else "LOCAL_REJECTED",
        "reason_codes": [] if upload_allowed else ["LOCAL_SCORE_BELOW_THRESHOLD"],
        "test_injection": "TEST_INJECTION" if force_low_score else None,
    }

