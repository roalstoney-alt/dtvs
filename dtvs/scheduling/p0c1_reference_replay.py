"""Arithmetic inspection of exported P0-C1 observations, never live placement.

The final tie priority and report layout must be supplied explicitly from a
reviewed reference. Neither is guessed from selected decisions or old fixtures.
"""
from __future__ import annotations

import csv
import io
import math
import re
from statistics import fmean, median

from dtvs.common.canonical_json import dumps
from dtvs.scheduling.historical_import import ArtifactError

NAMESPACE = "P0C1_LAN_V01"
ROUTES = {
    "A_CENTRAL_RELAY": "CENTRAL_RELAY",
    "B_DIRECT_SOURCE": "DIRECT_SOURCE",
    "C_IN_SITU": "IN_SITU",
    "D_STREAM_RANGE": "STREAM_RANGE",
}
PROFILES = ("OLD_WIFI", "NEW_WIFI")
QUERIES = ("Q1", "Q2")
SCENARIOS = {
    "LOCAL_ALLOWED": frozenset(ROUTES),
    "LOCAL_FORBIDDEN": frozenset({"A_CENTRAL_RELAY", "B_DIRECT_SOURCE", "D_STREAM_RANGE"}),
    "LOCAL_AND_RANGE_FORBIDDEN": frozenset({"A_CENTRAL_RELAY", "B_DIRECT_SOURCE"}),
    "RELAY_ONLY": frozenset({"A_CENTRAL_RELAY"}),
}
OBSERVATION_FIELDS = ("profile", "query", "path", "repeat", "status", "elapsed_s", "payload_bytes")
DECISION_FIELDS = (
    "profile", "scenario", "query", "heldout_repeat", "eligible_paths", "selected_path",
    "predicted_s", "actual_s", "oracle_s", "regret_pct", "payload_bytes", "decision_state",
)
STATISTICS = {
    "decision_count", "mean_predicted_s", "mean_actual_s", "mean_oracle_s",
    "mean_regret_pct", "max_regret_pct", "mean_payload_bytes", "selected_counts",
}


def _rows(content: bytes, fields: tuple[str, ...]) -> list[dict]:
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        if reader.fieldnames != list(fields):
            raise ArtifactError("CSV_SCHEMA_DRIFT")
        rows = []
        for row in reader:
            if len(rows) == 48:
                raise ArtifactError("CSV_CARDINALITY_INVALID")
            if None in row or any(not value or len(value) > 1024 for value in row.values()):
                raise ArtifactError("CSV_RECORD_MALFORMED")
            rows.append(row)
    except (UnicodeError, csv.Error):
        raise ArtifactError("CSV_ENCODING_OR_RECORD_INVALID") from None
    if len(rows) != 48:
        raise ArtifactError("CSV_CARDINALITY_INVALID")
    return rows


def _number(value: str, *, positive: bool = False) -> float:
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ArtifactError("CSV_NUMERIC_VALUE_INVALID") from None
    if not math.isfinite(number) or number < 0 or (positive and number == 0) or number > 1e12:
        raise ArtifactError("CSV_NUMERIC_VALUE_INVALID")
    return number


def _integer(value: str, *, repeat: bool = False) -> int:
    if not re.fullmatch(r"0|[1-9][0-9]{0,18}", value):
        raise ArtifactError("CSV_INTEGER_INVALID")
    number = int(value)
    if number > 2**63 - 1 or (repeat and number not in {1, 2, 3}):
        raise ArtifactError("CSV_INTEGER_INVALID")
    return number


def parse_exports(observations: bytes, decisions: bytes, report: dict) -> tuple[dict, list[dict]]:
    """Validate the complete fixed grid, not merely two counts of 48."""
    if report.get("status") != "OFFLINE_REPLAY_ONLY" or "policy" not in report:
        raise ArtifactError("REPORT_CONTRACT_INVALID")
    if any(type(report.get(name)) is not int or report[name] != 48 for name in ("observations", "holdout_decisions")):
        raise ArtifactError("REPORT_CARDINALITY_INVALID")
    samples = {}
    for row in _rows(observations, OBSERVATION_FIELDS):
        profile, query, route = row["profile"], row["query"], row["path"]
        if profile not in PROFILES or query not in QUERIES or route not in ROUTES:
            raise ArtifactError("PROFILE_QUERY_OR_ROUTE_SEMANTICS_INVALID")
        if row["status"] != "ACCEPTED":
            raise ArtifactError("OBSERVATION_STATUS_NOT_ACCEPTED")
        repeat = _integer(row["repeat"], repeat=True)
        key = profile, query, route, repeat
        if key in samples:
            raise ArtifactError("DUPLICATE_OBSERVATION")
        samples[key] = {
            "elapsed_s": _number(row["elapsed_s"], positive=True),
            "payload_bytes": _integer(row["payload_bytes"]),
        }
    expected_samples = {(p, q, r, k) for p in PROFILES for q in QUERIES for r in ROUTES for k in (1, 2, 3)}
    if set(samples) != expected_samples:
        raise ArtifactError("OBSERVATION_GRID_INCOMPLETE")
    for profile in PROFILES:
        for query in QUERIES:
            for route in ROUTES:
                if len({samples[profile, query, route, k]["payload_bytes"] for k in (1, 2, 3)}) != 1:
                    raise ArtifactError("PAYLOAD_NOT_CONSTANT_WITHIN_ROUTE")
    parsed, seen = [], set()
    for raw in _rows(decisions, DECISION_FIELDS):
        row = dict(raw)
        profile, query, scenario = row["profile"], row["query"], row["scenario"]
        if profile not in PROFILES or query not in QUERIES or scenario not in SCENARIOS or row["selected_path"] not in ROUTES:
            raise ArtifactError("DECISION_PROFILE_SCENARIO_OR_ROUTE_INVALID")
        row["heldout_repeat"] = _integer(row["heldout_repeat"], repeat=True)
        identity = profile, scenario, query, row["heldout_repeat"]
        if identity in seen:
            raise ArtifactError("DUPLICATE_DECISION")
        seen.add(identity)
        for name in ("predicted_s", "actual_s", "oracle_s", "regret_pct"):
            row[name] = _number(row[name], positive=name != "regret_pct")
        row["payload_bytes"] = _integer(row["payload_bytes"])
        parsed.append(row)
    expected_decisions = {(p, s, q, k) for p in PROFILES for s in SCENARIOS for q in QUERIES for k in (1, 2, 3)}
    if seen != expected_decisions:
        raise ArtifactError("DECISION_GRID_INCOMPLETE")
    return samples, parsed


def validate_reference(reference: dict) -> None:
    """Caller-selected policy/layout is an explicit reference, not an authority."""
    required = {
        "schema_version", "route_namespace", "source_reference_sha256", "tie_priority",
        "eligible_paths_encoding", "decision_state", "expected_report_policy",
        "csv_regret_decimals", "report_checks",
    }
    if not isinstance(reference, dict) or set(reference) != required:
        raise ArtifactError("POLICY_REFERENCE_SCHEMA_INVALID")
    if reference["schema_version"] != "p0c1-output-reference-v0.1" or reference["route_namespace"] != NAMESPACE:
        raise ArtifactError("POLICY_REFERENCE_VERSION_INVALID")
    priority = reference["tie_priority"]
    if not isinstance(priority, list) or len(priority) != 4 or any(not isinstance(path, str) for path in priority) or set(priority) != set(ROUTES):
        raise ArtifactError("EXPLICIT_FINAL_TIE_PRIORITY_REQUIRED")
    if not isinstance(reference["source_reference_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", reference["source_reference_sha256"]):
        raise ArtifactError("POLICY_REFERENCE_HASH_INVALID")
    if reference["eligible_paths_encoding"] not in {"JSON_ARRAY", "PIPE_SEPARATED"}:
        raise ArtifactError("ELIGIBLE_PATHS_ENCODING_UNSUPPORTED")
    if not isinstance(reference["decision_state"], str) or not reference["decision_state"] or len(reference["decision_state"]) > 128:
        raise ArtifactError("EXPLICIT_DECISION_STATE_REQUIRED")
    if type(reference["csv_regret_decimals"]) is not int or not 0 <= reference["csv_regret_decimals"] <= 9:
        raise ArtifactError("REGRET_PRECISION_INVALID")
    checks = reference["report_checks"]
    if not isinstance(checks, list) or not 33 <= len(checks) <= 100:
        raise ArtifactError("REPORT_CHECK_COVERAGE_REQUIRED")
    identities, pointers = set(), set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"pointer", "profile", "scenario", "statistic", "decimals"}:
            raise ArtifactError("REPORT_CHECK_SCHEMA_INVALID")
        profile, scenario, statistic = check["profile"], check["scenario"], check["statistic"]
        if not ((profile in PROFILES and scenario in SCENARIOS) or (profile is None and scenario is None)) or statistic not in STATISTICS:
            raise ArtifactError("REPORT_CHECK_SCOPE_INVALID")
        pointer = check["pointer"]
        if not isinstance(pointer, str) or not pointer.startswith("/") or len(pointer) > 256:
            raise ArtifactError("REPORT_POINTER_INVALID")
        identity = profile, scenario, statistic
        if identity in identities or pointer in pointers:
            raise ArtifactError("DUPLICATE_REPORT_CHECK")
        identities.add(identity)
        pointers.add(pointer)
        if type(check["decimals"]) is not int or not 0 <= check["decimals"] <= 9:
            raise ArtifactError("REPORT_PRECISION_INVALID")
    minimum = {(p, s, name) for p in PROFILES for s in SCENARIOS for name in ("decision_count", "mean_actual_s", "mean_regret_pct", "max_regret_pct")}
    if not minimum <= identities or (None, None, "max_regret_pct") not in identities:
        raise ArtifactError("REPORT_CHECK_COVERAGE_REQUIRED")


def _eligible(raw: str, encoding: str) -> set[str]:
    if encoding == "JSON_ARRAY":
        import json
        try:
            paths = json.loads(raw)
        except ValueError:
            raise ArtifactError("ELIGIBLE_PATHS_INVALID") from None
    else:
        paths = raw.split("|")
    if not isinstance(paths, list) or any(not isinstance(path, str) or path not in ROUTES for path in paths) or len(paths) != len(set(paths)):
        raise ArtifactError("ELIGIBLE_PATHS_INVALID")
    return set(paths)


def forecast(training: dict[str, list[dict]], feasible: set[str], priority: list[str]) -> tuple[str, dict[str, float]]:
    """Accept only two training samples per route; no held-out times or oracle."""
    if any(len(training[route]) != 2 for route in feasible):
        raise ArtifactError("TWO_OTHER_REPEATS_REQUIRED")
    predictions = {route: median(row["elapsed_s"] for row in training[route]) for route in feasible}
    cutoff = min(predictions.values()) * 1.03
    near = [route for route in feasible if predictions[route] <= cutoff]
    selected = min(near, key=lambda route: (training[route][0]["payload_bytes"], priority.index(route)))
    return selected, predictions


def _matches(actual: float, expected: float, decimals: int) -> bool:
    return math.isfinite(actual) and abs(actual - expected) <= .5 * 10**(-decimals) + 1e-10


def _statistics(rows: list[dict]) -> dict:
    return {
        "decision_count": len(rows),
        "mean_predicted_s": fmean(row["predicted_s"] for row in rows),
        "mean_actual_s": fmean(row["actual_s"] for row in rows),
        "mean_oracle_s": fmean(row["oracle_s"] for row in rows),
        "mean_regret_pct": fmean(row["regret_pct"] for row in rows),
        "max_regret_pct": max(row["regret_pct"] for row in rows),
        "mean_payload_bytes": fmean(row["payload_bytes"] for row in rows),
        "selected_counts": {path: sum(row["selected_path"] == path for row in rows) for path in ROUTES},
    }


def reconstruct(samples: dict, decisions: list[dict], reference: dict, report: dict) -> tuple[dict, dict]:
    validate_reference(reference)
    if dumps(report["policy"]) != dumps(reference["expected_report_policy"]):
        raise ArtifactError("REPORT_POLICY_REFERENCE_MISMATCH")
    recomputed = []
    for row in sorted(decisions, key=lambda d: (d["profile"], d["scenario"], d["query"], d["heldout_repeat"])):
        profile, query, heldout = row["profile"], row["query"], row["heldout_repeat"]
        feasible = SCENARIOS[row["scenario"]]
        if _eligible(row["eligible_paths"], reference["eligible_paths_encoding"]) != feasible:
            raise ArtifactError("HYPOTHETICAL_FEASIBLE_SET_MISMATCH")
        if row["decision_state"] != reference["decision_state"]:
            raise ArtifactError("DECISION_STATE_REFERENCE_MISMATCH")
        training = {route: [samples[profile, query, route, k] for k in (1, 2, 3) if k != heldout] for route in feasible}
        selected, predictions = forecast(training, feasible, reference["tie_priority"])
        if selected != row["selected_path"]:
            raise ArtifactError("DECISION_MISRANKED")
        actual = samples[profile, query, selected, heldout]["elapsed_s"]
        oracle = min(samples[profile, query, route, heldout]["elapsed_s"] for route in feasible)
        regret = (actual / oracle - 1) * 100
        expected = {"predicted_s": predictions[selected], "actual_s": actual, "oracle_s": oracle, "regret_pct": regret}
        for name, value in expected.items():
            if not _matches(row[name], value, reference["csv_regret_decimals"] if name == "regret_pct" else 4):
                raise ArtifactError("EXPORTED_" + name.upper() + "_MISMATCH")
        payload = samples[profile, query, selected, heldout]["payload_bytes"]
        if row["payload_bytes"] != payload:
            raise ArtifactError("DECISION_PAYLOAD_MISMATCH")
        recomputed.append({**expected, "payload_bytes": payload, "selected_path": selected, "profile": profile, "scenario": row["scenario"]})
    groups = {(p, s): _statistics([row for row in recomputed if (row["profile"], row["scenario"]) == (p, s)]) for p in PROFILES for s in SCENARIOS}
    overall = _statistics(recomputed)
    summary = {
        "matched_predictions": 48, "matched_selections": 48, "matched_actuals": 48,
        "matched_oracles": 48, "matched_regrets": 48, "matched_payloads": 48,
        "unique_exported_holdout_folds": 12, "scenarios_per_reused_fold": 4,
        "hypothetical_feasibility_violations": 0, "heldout_time_leakage_count": 0,
        "max_regret_pct": overall["max_regret_pct"],
    }
    return summary, {"groups": groups, "overall": overall}


def validate_report_statistics(report: dict, statistics: dict, reference: dict) -> int:
    for check in reference["report_checks"]:
        expected = statistics["overall"] if check["profile"] is None else statistics["groups"][check["profile"], check["scenario"]]
        value = report
        try:
            for token in check["pointer"].split("/")[1:]:
                token = token.replace("~1", "/").replace("~0", "~")
                value = value[int(token)] if isinstance(value, list) else value[token]
        except (KeyError, IndexError, TypeError, ValueError):
            raise ArtifactError("REPORT_STATISTICS_LAYOUT_MISMATCH") from None
        expected_value = expected[check["statistic"]]
        if check["statistic"] == "decision_count":
            matches = type(value) is int and value == expected_value
        elif isinstance(expected_value, dict):
            matches = value == expected_value and all(type(v) is int for v in value.values())
        else:
            matches = type(value) in (int, float) and _matches(value, expected_value, check["decimals"])
        if not matches:
            raise ArtifactError("REPORT_STATISTIC_MISMATCH")
    return len(reference["report_checks"])
