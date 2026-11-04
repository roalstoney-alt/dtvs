"""Directional calibration gates; a benchmark is never permanent capacity."""
from __future__ import annotations

import json
import hashlib
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from dtvs.common.canonical_json import dumps

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"


def validate_schema(document: dict, name: str) -> None:
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() != timedelta(0):
        raise ValueError("explicit UTC timestamp required")
    return result


def calibration_reasons(
    profile: dict[str, Any] | None, *, source_id: str, destination_id: str,
    topology_id: str | None, as_of: str, source_record: dict | None,
) -> list[str]:
    """Return fail-closed reasons without mutating or probing the network."""
    reasons = []
    if profile is None:
        return ["PROFILE_MISSING"]
    try:
        validate_schema(profile, "network_profile_v01.schema.json")
        now = utc(as_of)
        recorded = utc(profile["recorded_at"])
        start = utc(profile["observation_window"]["start"])
        end = utc(profile["observation_window"]["end"])
    except (ValueError, TypeError, KeyError, ValidationError):
        return ["PROFILE_INVALID"]
    if (profile["source_id"], profile["destination_id"]) != (source_id, destination_id):
        reasons.append("DIRECTION_MISMATCH")
    if not topology_id or profile["route_context"]["topology_id"] != topology_id:
        reasons.append("UNKNOWN_TOPOLOGY")
    if not start <= end <= recorded <= now:
        reasons.append("PROFILE_TIME_INVALID")
    # Age the observation, not a freshly rewritten recorded_at field.
    if (now - end).total_seconds() > profile["ttl_seconds"]:
        reasons.append("PROFILE_STALE")
    if not isinstance(source_record, dict) or hashlib.sha256(dumps(source_record)).hexdigest() != profile["source_sha256"]:
        reasons.append("PROFILE_SOURCE_HASH_MISMATCH")
    elif any(source_record.get(name) != value for name, value in profile.items() if name not in {"source_sha256", "ttl_seconds", "profile_id"}):
        reasons.append("PROFILE_SOURCE_CONTENT_MISMATCH")
    if profile["observed_mbps"] is None or profile["conservative_mbps"] is None:
        reasons.append("THROUGHPUT_NOT_MEASURED")
    elif profile["conservative_mbps"] > profile["observed_mbps"]:
        reasons.append("CONSERVATIVE_THROUGHPUT_INVALID")
    if any(value is not None and not math.isfinite(value) for value in (
        profile["observed_mbps"], profile["conservative_mbps"], profile["variability_mbps"],
    )):
        reasons.append("PROFILE_NONFINITE_VALUE")
    if profile["anomaly_flags"]:
        reasons.append("PROFILE_ANOMALY_UNRESOLVED")
    return reasons
