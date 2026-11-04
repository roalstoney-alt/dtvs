"""Signed offline eligibility assertions precede any latency ranking.

These assertions are supplied by an operator, not inferred from observations.
They do not grant access, dispatch work, issue verdicts, or authorize a merge.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import ValidationError

from dtvs.common.canonical_json import dumps
from dtvs.contracts.signing import verify_document
from dtvs.scheduling.network_profile import calibration_reasons, utc, validate_schema

MODES = {"LOCAL", "DIRECT", "RANGE", "REMOTE"}
COMMON_PERMISSIONS = (
    "task_input_authorized", "asset_authorized", "source_access_allowed",
    "compute_capable", "privacy_allowed", "legal_allowed",
)


def digest(value: Any) -> str:
    return hashlib.sha256(dumps(value)).hexdigest()


def task_gate(task: dict, fixture: bytes, trusted_key: Ed25519PublicKey, as_of: str) -> list[str]:
    """Verify the actual Bundle and a separate, Bundle-bound authorization.

    The existing v0.2.2 Bundle schema and signed bytes are not extended or
    rewritten. Authority for the supplied public key remains an external gate.
    """
    try:
        bundle, authorization = task["bundle"], task["authorization"]
        validate_schema(bundle, "task_bundle_v022.schema.json")
        if not verify_document(bundle, trusted_key) or not verify_document(authorization, trusted_key):
            return ["HOLD_INTEGRITY", "SIGNATURE_INVALID"]
        fixture_hash = hashlib.sha256(fixture).hexdigest()
        if (
            bundle["input"]["sha256"] != fixture_hash
            or bundle["asset_id"] != "sha256:" + fixture_hash
            or authorization["fixture_sha256"] != fixture_hash
            or authorization["bundle_sha256"] != digest(bundle)
            or authorization["task_id"] != bundle["task_id"]
            or task["task_id"] != bundle["task_id"]
            or authorization["environment_profile_id"] != task["environment_profile_id"]
        ):
            return ["HOLD_INTEGRITY", "INPUT_OR_BUNDLE_HASH_MISMATCH"]
        if utc(bundle["lease"]["expires_at"]) <= utc(as_of):
            return ["HOLD_QUALITY_GATE", "LEASE_EXPIRED"]
        if authorization.get("bundle_state") not in {"CREATED", "LEASED"}:
            return ["HOLD_QUALITY_GATE", "BUNDLE_STATE_NOT_SCHEDULABLE"]
        for name in ("verifier_required", "accepted_only_merge", "quality_gate_required"):
            if authorization.get(name) is None:
                return ["HOLD_ELIGIBILITY_UNKNOWN", name.upper()]
            if authorization[name] is not True:
                return ["HOLD_QUALITY_GATE", name.upper()]
        verification = bundle["verification"]
        for name, minimum in (("upload_threshold", 90), ("minimum_component_score", 70)):
            value = verification[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= 100:
                return ["HOLD_QUALITY_GATE", "BUNDLE_QUALITY_THRESHOLD_WEAKENED"]
        candidates = authorization["candidates"]
        if not candidates or len({c["route_id"] for c in candidates}) != len(candidates):
            return ["HOLD_ELIGIBILITY_UNKNOWN", "CANDIDATES_INVALID"]
        if len({c["mode"] for c in candidates}) != len(candidates):
            return ["HOLD_ELIGIBILITY_UNKNOWN", "AMBIGUOUS_ROUTE_MODE"]
    except (KeyError, TypeError, ValueError, ValidationError):
        return ["HOLD_INTEGRITY", "TASK_INVALID"]
    return []


def candidate_gate(candidate: dict, profiles: dict[str, dict], *, as_of: str, profile_sources: dict[str, dict]) -> dict:
    """Known denials are infeasible. Unknown permissions/calibration HOLD."""
    unknown, denied, calibration = [], [], []
    try:
        mode = candidate["mode"]
        if mode not in MODES:
            raise ValueError("mode")
        permissions = candidate["permissions"]
        required = COMMON_PERMISSIONS + (("source_execution_allowed",) if mode == "LOCAL" else ("remote_execution_allowed",))
        if mode == "RANGE":
            required += ("range_supported",)
        for name in required:
            value = permissions.get(name)
            if value is False:
                denied.append("DENIED_" + name.upper())
            elif value is not True:
                unknown.append("UNKNOWN_" + name.upper())
        fraction = candidate.get("access_fraction")
        if not isinstance(fraction, (int, float)) or isinstance(fraction, bool) or not math.isfinite(fraction) or not 0 < fraction <= 1:
            unknown.append("ACCESS_FRACTION_UNKNOWN")
        elif mode in {"LOCAL", "DIRECT", "REMOTE"} and fraction != 1:
            unknown.append("FULL_ACCESS_FRACTION_REQUIRED")
        if denied:
            return {"status": "INELIGIBLE", "reason_codes": sorted(denied + unknown)}
        if unknown:
            return {"status": "HOLD_ELIGIBILITY_UNKNOWN", "reason_codes": sorted(unknown)}
        hops = candidate["network_hops"]
        if not candidate.get("topology_id"):
            calibration.append("UNKNOWN_TOPOLOGY")
        if mode == "LOCAL":
            if hops or candidate["source_id"] != candidate["destination_id"]:
                calibration.append("LOCAL_TOPOLOGY_INVALID")
        else:
            # Require both input and result directions, even for a small result.
            endpoints = (candidate["source_id"], candidate["destination_id"])
            if endpoints[0] == endpoints[1] or len(hops) != 2 or {
                (hop["source_id"], hop["destination_id"]) for hop in hops
            } != {endpoints, endpoints[::-1]}:
                calibration.append("NETWORK_DIRECTIONS_INCOMPLETE")
            for hop in hops:
                calibration += calibration_reasons(
                    profiles.get(hop.get("profile_id")), source_id=hop["source_id"],
                    destination_id=hop["destination_id"], topology_id=candidate.get("topology_id"),
                    as_of=as_of, source_record=profile_sources.get(hop.get("profile_id")),
                )
    except (KeyError, TypeError, ValueError):
        return {"status": "HOLD_ELIGIBILITY_UNKNOWN", "reason_codes": ["CANDIDATE_INVALID"]}
    return {
        "status": "HOLD_NOT_CALIBRATED" if calibration else "ELIGIBLE",
        "reason_codes": sorted(set(calibration)) or ["ALL_GATES_PASS"],
    }


def rank(predictions: dict[str, float]) -> str:
    """Predictions only: no held-out times or oracle input is accepted here."""
    if not predictions or any(not math.isfinite(v) or v <= 0 for v in predictions.values()):
        raise ValueError("positive finite predictions required")
    return min(predictions, key=lambda route: (predictions[route], route))
