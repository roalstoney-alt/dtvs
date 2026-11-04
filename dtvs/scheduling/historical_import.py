"""Opt-in, output-artifact validation for sanitized P0-C1 operator exports.

This is an inspection path, not an adapter into the signed synthetic replay.
It never creates permissions, signatures, placements, or historical acceptance.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat

from dtvs.common.canonical_json import dumps
from dtvs.scheduling.historical_routes import SPEC_VERSION, classify_route

IMPORT_VERSION = "p0c1-sanitized-import-v0.1"
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
ARTIFACT_NAMES = {"report.md", "report.json", "decisions.csv"}
HEX_SHA256 = re.compile(r"[a-f0-9]{64}")
CSV_FIELDS = {"environment_profile_id", "task_id", "repeat_id", "source_route_id"}


class ArtifactError(ValueError):
    """Only controlled reason codes, never untrusted values or source paths."""


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _json(content: bytes) -> dict:
    def reject_constant(value: str) -> None:
        raise ArtifactError("NONFINITE_JSON_VALUE")

    try:
        value = json.loads(content, object_pairs_hook=_object, parse_constant=reject_constant)
        # Reject overflow floats and invalid escaped Unicode, even in unused fields.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except ArtifactError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise ArtifactError("ARTIFACT_JSON_INVALID") from None
    if not isinstance(value, dict):
        raise ArtifactError("ARTIFACT_OBJECT_REQUIRED")
    return value


def _read(folder: Path, name: str) -> bytes:
    # Callers supply fixed allowed basenames. Never follow manifest-provided paths.
    if not hasattr(os, "O_NOFOLLOW"):
        raise ArtifactError("SAFE_FILE_OPEN_UNSUPPORTED")
    try:
        fd = os.open(folder / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARTIFACT_BYTES:
                raise ArtifactError("ARTIFACT_TYPE_OR_SIZE_INVALID")
            content = stream.read(MAX_ARTIFACT_BYTES + 1)
            if len(content) > MAX_ARTIFACT_BYTES:
                raise ArtifactError("ARTIFACT_TYPE_OR_SIZE_INVALID")
            return content
    except OSError:
        raise ArtifactError("ARTIFACT_UNAVAILABLE_OR_SYMLINK") from None


def _initial_result() -> dict:
    return {
        "schema_version": IMPORT_VERSION, "route_spec_version": SPEC_VERSION,
        "status": "HOLD_PROVENANCE", "reason_codes": [],
        "input_mode": "SANITIZED_P0C1_ARTIFACT_INSPECTION",
        "claimed_source_input_mode": None, "manifest_sha256": None,
        "listed_files_sha256": {}, "validated_files_sha256": {},
        "artifact_validation": "NOT_COMPLETED", "reported_counts": None,
        "route_mappings": [], "csv_rows_validated": None,
        "raw_content_authenticity": "NOT_VERIFIED",
        "event_chain_validation": "NOT_PERFORMED_NO_RAW_EVENTS",
        "external_provenance_anchor": "NOT_VERIFIED",
        "permissions_status": "HOLD_ELIGIBILITY_UNKNOWN",
        "historical_performance_acceptance": "HOLD",
        "production_dispatch": "DISABLED", "merge": "NO", "deploy": "NO",
        "selected_route": None, "historical_regret": None,
        "audit": {
            "PRODUCTION_DISPATCH_COUNT": 0, "EXTERNAL_NETWORK_ACTIONS": 0,
            "CLOUD_BILLABLE_ACTIONS": 0, "signatures_created": 0,
            "permission_assertions_created": 0, "placements_created": 0,
        },
    }


def _mapping_inventory(report: dict, result: dict) -> set[tuple[str, str]]:
    records = report.get("route_semantics")
    if not isinstance(records, list) or not records:
        result["reason_codes"].append("ROUTE_SEMANTICS_NOT_SUPPLIED")
        return set()
    identities = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ArtifactError("ROUTE_SEMANTIC_RECORD_INVALID")
        environment, route_id = record.get("environment_profile_id"), record.get("source_route_id")
        if not isinstance(environment, str) or not environment or not isinstance(route_id, str) or not route_id:
            raise ArtifactError("ROUTE_PROFILE_OR_ID_REQUIRED")
        identity = (environment, route_id)
        if identity in identities:
            raise ArtifactError("DUPLICATE_ROUTE_SEMANTICS")
        identities.add(identity)
        mapping = classify_route(record)
        mapping.update(record_index=index, environment_profile_sha256=_sha(environment.encode()))
        result["route_mappings"].append(mapping)
        if mapping["status"] != "MAPPED_SEMANTICS_ONLY":
            result["reason_codes"].append("HOLD_SEMANTIC_MAPPING")
    return identities


def _validate_csv(content: bytes, report: dict, route_identities: set[tuple[str, str]]) -> int:
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not CSV_FIELDS <= set(fields):
            raise ArtifactError("DECISIONS_CSV_LAYOUT_UNSUPPORTED")
        seen, count = set(), 0
        for row in reader:
            if None in row or any(not row.get(name) for name in CSV_FIELDS):
                raise ArtifactError("DECISIONS_CSV_ROW_INVALID")
            identity = tuple(row[name] for name in ("environment_profile_id", "task_id", "repeat_id"))
            if identity in seen:
                raise ArtifactError("DUPLICATE_DECISION_ROW")
            seen.add(identity)
            if (row["environment_profile_id"], row["source_route_id"]) not in route_identities:
                raise ArtifactError("DECISION_ROUTE_SEMANTICS_UNAVAILABLE")
            count += 1
    except (UnicodeError, csv.Error):
        raise ArtifactError("DECISIONS_CSV_INVALID") from None
    if count != report["holdout_decisions"]:
        raise ArtifactError("DECISION_COUNT_MISMATCH")
    return count


def inspect_sanitized_artifacts(input_dir: Path, *, opt_in: bool = False) -> dict:
    """Read only a caller-selected sanitized directory, after explicit opt-in.

    Even fully consistent output hashes and semantic metadata cannot discharge
    historical provenance, raw-content, permission, or acceptance gates.
    """
    if opt_in is not True:
        raise PermissionError("SANITIZED_IMPORT_OPT_IN_REQUIRED")
    result = _initial_result()
    try:
        manifest_bytes = _read(input_dir, "manifest.json")
        result["manifest_sha256"] = _sha(manifest_bytes)
        manifest = _json(manifest_bytes)
        files = manifest.get("files_sha256")
        if not isinstance(files, dict) or not {"report.md", "report.json"} <= set(files) or not set(files) <= ARTIFACT_NAMES:
            raise ArtifactError("SANITIZED_MANIFEST_FILE_SET_UNSUPPORTED")
        if any(not isinstance(value, str) or not HEX_SHA256.fullmatch(value) for value in files.values()):
            raise ArtifactError("MANIFEST_DIGEST_INVALID")
        result["listed_files_sha256"] = dict(sorted(files.items()))
        sources = {}
        for name, expected in sorted(files.items()):
            content = _read(input_dir, name)
            if _sha(content) != expected:
                raise ArtifactError("ARTIFACT_HASH_MISMATCH")
            result["validated_files_sha256"][name] = expected
            sources[name] = content
        result["artifact_validation"] = "LISTED_OUTPUT_HASHES_MATCH"
        if manifest.get("input_mode") != "RAW_RUN_FILES":
            raise ArtifactError("RAW_RUN_FILES_CLAIM_REQUIRED")
        result["claimed_source_input_mode"] = "RAW_RUN_FILES"
        report = _json(sources["report.json"])
        if report.get("status") != "OFFLINE_REPLAY_ONLY":
            raise ArtifactError("OFFLINE_REPORT_STATUS_REQUIRED")
        for name in ("observations", "holdout_decisions"):
            if type(report.get(name)) is not int or report[name] <= 0:
                raise ArtifactError("REPORT_COUNTS_INVALID")
        result["reported_counts"] = {name: report[name] for name in ("observations", "holdout_decisions")}
        identities = _mapping_inventory(report, result)
        if "decisions.csv" in sources:
            result["csv_rows_validated"] = _validate_csv(sources["decisions.csv"], report, identities)
        else:
            result["reason_codes"].append("DECISIONS_CSV_NOT_SUPPLIED")
        if any(name not in files and (input_dir / name).exists() for name in ARTIFACT_NAMES):
            result["reason_codes"].append("UNMANIFESTED_ARTIFACT_NOT_IMPORTED")
    except ArtifactError as error:
        result["status"] = "HOLD_ARTIFACT_VALIDATION"
        result["reason_codes"].append(str(error))
    result["reason_codes"] = sorted(set(result["reason_codes"] + [
        "RAW_CONTENT_NOT_INDEPENDENTLY_VERIFIED", "EVENT_CHAIN_NOT_EXTERNALLY_ANCHORED",
        "HISTORICAL_PERMISSION_EVIDENCE_NOT_VERIFIED", "HUMAN_PROVENANCE_REVIEW_REQUIRED",
    ]))
    return result


def write_inspection(input_dir: Path, output_dir: Path, *, opt_in: bool = False) -> dict:
    result = inspect_sanitized_artifacts(input_dir, opt_in=opt_in)
    output_dir.mkdir(parents=True, exist_ok=False)
    payload = dumps(result) + b"\n"
    manifest = {
        "schema_version": IMPORT_VERSION, "status": result["status"],
        "source_manifest_sha256": result["manifest_sha256"],
        "source_files_sha256": result["validated_files_sha256"],
        "files_sha256": {"validation.json": _sha(payload)},
        "provenance": "SELF_CONTAINED_HASHES_NOT_EXTERNALLY_ANCHORED",
    }
    for name, content in (("validation.json", payload), ("manifest.json", dumps(manifest) + b"\n")):
        with (output_dir / name).open("xb") as stream:
            stream.write(content)
        (output_dir / name).chmod(0o444)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-sanitized-p0c1-import", action="store_true")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.allow_sanitized_p0c1_import:
        print(json.dumps({"status": "OPT_IN_REQUIRED", "reason_codes": ["SANITIZED_IMPORT_OPT_IN_REQUIRED"]}))
        return 3
    try:
        result = write_inspection(args.input_dir, args.output_dir, opt_in=True)
    except OSError:
        print(json.dumps({"status": "OUTPUT_REFUSED", "reason_codes": ["NEW_WRITABLE_OUTPUT_DIRECTORY_REQUIRED"]}))
        return 4
    print(json.dumps(result, sort_keys=True))
    # A successful inspection is still a HOLD, never an acceptance exit.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
