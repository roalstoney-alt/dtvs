"""P0-C1 semantic classification only; never a placement or permission grant."""
from __future__ import annotations

import hashlib

from dtvs.common.canonical_json import dumps

NAMESPACE = "P0C1_LAN_V01"
SPEC_VERSION = "p0c1-route-semantics-v0.1"
HISTORICAL_LETTERS = {
    "A": "CENTRAL_RELAY",
    "B": "DIRECT_SOURCE",
    "C": "IN_SITU",
    "D": "STREAM_RANGE",
}

# Execution site, input role path, input access. Roles do not identify hosts.
# Classify by these facts first; letter aliases are only consistency checks.
SEMANTICS = {
    "CENTRAL_RELAY": ("WORKER", ("SOURCE", "CENTRAL", "WORKER"), "FULL_OBJECT"),
    "DIRECT_SOURCE": ("WORKER", ("SOURCE", "WORKER"), "FULL_OBJECT"),
    "IN_SITU": ("SOURCE", ("SOURCE",), "IN_PLACE"),
    "STREAM_RANGE": ("WORKER", ("SOURCE", "WORKER"), "BYTE_RANGE_STREAM"),
}


def classify_route(record: dict) -> dict:
    """Match explicitly declared semantics, never letters/modes/timing alone.

    Even a successful classification says nothing about the truth of the
    declaration, historical permissions, transport direction, or feasibility.
    Arbitrary input identifiers are hashed rather than echoed into outputs.
    """
    route_id = record.get("source_route_id")
    valid_id = isinstance(route_id, str) and 0 < len(route_id) <= 128
    result = {
        "spec_version": SPEC_VERSION,
        "source_route_label": route_id if valid_id and route_id in HISTORICAL_LETTERS else None,
        "source_route_id_sha256": hashlib.sha256(route_id.encode()).hexdigest() if valid_id else None,
        "semantic_record_sha256": hashlib.sha256(dumps(record)).hexdigest(),
        "status": "HOLD_SEMANTIC_MAPPING", "canonical_route": None,
        "reason_codes": [],
    }
    if record.get("route_namespace") != NAMESPACE or not valid_id:
        result["reason_codes"] = ["EXPLICIT_HISTORICAL_NAMESPACE_AND_ID_REQUIRED"]
        return result
    required = ("execution_site", "input_path", "input_access")
    if any(name not in record for name in required):
        result["reason_codes"] = ["STRUCTURAL_ROUTE_EVIDENCE_REQUIRED"]
        return result
    path = record["input_path"]
    if not isinstance(path, list) or any(not isinstance(role, str) for role in path):
        result["reason_codes"] = ["INPUT_ROLE_PATH_INVALID"]
        return result
    facts = (record["execution_site"], tuple(path), record["input_access"])
    canonical = next((name for name, expected in SEMANTICS.items() if facts == expected), None)
    if canonical is None:
        result["reason_codes"] = ["UNSUPPORTED_OR_CONFLICTING_ROUTE_SEMANTICS"]
    elif record.get("declared_canonical_route", canonical) != canonical:
        result["reason_codes"] = ["DECLARED_CANONICAL_ROUTE_CONFLICT"]
    elif route_id in HISTORICAL_LETTERS and HISTORICAL_LETTERS[route_id] != canonical:
        result["reason_codes"] = ["HISTORICAL_LETTER_SEMANTICS_CONFLICT"]
    else:
        result.update(status="MAPPED_SEMANTICS_ONLY", canonical_route=canonical,
                      reason_codes=["EXPLICIT_STRUCTURAL_SEMANTICS_MATCH"])
    return result
