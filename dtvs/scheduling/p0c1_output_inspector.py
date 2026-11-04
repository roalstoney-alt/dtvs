"""Opt-in read-only inspection of the five-file P0-C1 output export.

All results HOLD historical provenance/permissions. Only controlled derived
summaries are emitted; source JSON, CSV rows, paths and tokens are never echoed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import zipfile
import zlib

from dtvs.common.canonical_json import dumps
from dtvs.scheduling.historical_import import ArtifactError, _json, _read
from dtvs.scheduling.p0c1_reference_replay import (
    NAMESPACE, ROUTES, parse_exports, reconstruct, validate_report_statistics,
)

VERSION = "p0c1-five-output-inspector-v0.2"
DATA_NAMES = {"report.json", "report.md", "observations.csv", "decisions.csv"}
MEMBER_NAMES = DATA_NAMES | {"manifest.json"}
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _archive_bytes(path: Path) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_TOTAL_BYTES:
                raise ArtifactError("ARCHIVE_RESOURCE_LIMIT")
            data = stream.read(MAX_TOTAL_BYTES + 1)
            if len(data) > MAX_TOTAL_BYTES:
                raise ArtifactError("ARCHIVE_RESOURCE_LIMIT")
            return data
    except OSError:
        raise ArtifactError("SOURCE_UNAVAILABLE_OR_SYMLINK") from None


def load_members(source: Path) -> tuple[dict[str, bytes], str, str | None]:
    """No extraction and no nested paths. CRC and decompression limits apply."""
    if not hasattr(os, "O_NOFOLLOW"):
        raise ArtifactError("SAFE_FILE_OPEN_UNSUPPORTED")
    if source.is_symlink():
        raise ArtifactError("SOURCE_UNAVAILABLE_OR_SYMLINK")
    if source.is_dir():
        members = {name: _read(source, name) for name in sorted(MEMBER_NAMES)}
        if sum(map(len, members.values())) > MAX_TOTAL_BYTES:
            raise ArtifactError("ARTIFACT_TOTAL_RESOURCE_LIMIT")
        return members, "DIRECTORY", None
    data = _archive_bytes(source)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) != 5 or {info.filename for info in entries} != MEMBER_NAMES:
                raise ArtifactError("ARCHIVE_MEMBER_SET_OR_DUPLICATE_INVALID")
            if sum(info.file_size for info in entries) > MAX_TOTAL_BYTES:
                raise ArtifactError("ARCHIVE_RESOURCE_LIMIT")
            members = {}
            for info in entries:
                kind = stat.S_IFMT(info.external_attr >> 16)
                if info.is_dir() or info.orig_filename != info.filename or kind not in {0, stat.S_IFREG} or info.flag_bits & 1:
                    raise ArtifactError("ILLEGAL_ARCHIVE_ENTRY")
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise ArtifactError("ARCHIVE_COMPRESSION_UNSUPPORTED")
                if info.file_size > MAX_MEMBER_BYTES or info.file_size > max(1, info.compress_size) * 200:
                    raise ArtifactError("ARCHIVE_RESOURCE_LIMIT")
                with archive.open(info) as stream:
                    content = stream.read(MAX_MEMBER_BYTES + 1)
                if len(content) != info.file_size or len(content) > MAX_MEMBER_BYTES:
                    raise ArtifactError("ARCHIVE_RESOURCE_LIMIT")
                members[info.filename] = content
    except (zipfile.BadZipFile, RuntimeError, EOFError, NotImplementedError, zlib.error):
        raise ArtifactError("ARCHIVE_CRC_OR_FORMAT_INVALID") from None
    return members, "ZIP", _sha(data)


def _initial() -> dict:
    return {
        "schema_version": VERSION, "status": "HOLD_PROVENANCE",
        "validation_status": "NOT_COMPLETED", "reason_codes": [],
        "route_namespace": NAMESPACE, "source_kind": None, "source_zip_sha256": None,
        "source_member_sha256": {}, "policy_reference_canonical_sha256": None,
        "policy_source_authenticity": "NOT_VERIFIED",
        "stages": {
            "internal_hash_verification": "NOT_RUN", "exported_grid": "NOT_RUN",
            "arithmetic": "NOT_RUN", "report_statistics": "NOT_RUN",
            "profile_isolation": "NOT_RUN", "structural_semantics": "HOLD",
            "placement_policy": "NOT_RUN",
        },
        "semantic_reference": {
            "basis": "SUPPLIED_REVIEW_002_DESCRIPTION_NOT_RUNTIME_ATTESTATION",
            "routes": ROUTES.copy(),
            "relay_stage": "MAC_LOCAL_COPY_AFTER_FULL_SOURCE_FETCH",
            "relay_requires_third_physical_host": False,
            "runtime_attestation": "NOT_VERIFIED",
        },
        "observations": None, "hypothetical_decisions": None,
        "unique_exported_holdout_folds": None, "scenarios_per_reused_fold": None,
        "arithmetic_summary": None, "group_statistics": [],
        "external_source_authenticity": "NOT_VERIFIED",
        "event_chain_validation": "NOT_PERFORMED_ORIGINAL_INPUTS_ABSENT",
        "historical_permissions": "HOLD", "permissions_status": "HOLD_ELIGIBILITY_UNKNOWN",
        "historical_performance_acceptance": "HOLD",
        "production_dispatch": "DISABLED", "merge": "NO", "deploy": "NO",
        "audit": {
            "PRODUCTION_DISPATCH_COUNT": 0, "EXTERNAL_NETWORK_ACTIONS": 0,
            "CLOUD_BILLABLE_ACTIONS": 0, "historical_signatures_created": 0,
            "permission_assertions_created": 0, "placements_created": 0,
        },
    }


def inspect_outputs(source: Path, *, opt_in: bool = False, reference_policy: dict | None = None) -> dict:
    if opt_in is not True:
        raise PermissionError("OUTPUT_INSPECTION_OPT_IN_REQUIRED")
    result = _initial()
    try:
        members, kind, zip_hash = load_members(source)
        result.update(source_kind=kind, source_zip_sha256=zip_hash)
        result["source_member_sha256"] = {name: _sha(content) for name, content in sorted(members.items())}
        manifest = _json(members["manifest.json"])
        files = manifest.get("files_sha256")
        if manifest.get("input_mode") != "RAW_RUN_FILES" or not isinstance(files, dict) or set(files) != DATA_NAMES:
            raise ArtifactError("EXACT_OUTPUT_MANIFEST_REQUIRED")
        if any(not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value) for value in files.values()):
            raise ArtifactError("MANIFEST_DIGEST_INVALID")
        if any(_sha(members[name]) != expected for name, expected in files.items()):
            raise ArtifactError("OUTPUT_MEMBER_HASH_MISMATCH")
        result["stages"]["internal_hash_verification"] = "PASS_SELF_CONTAINED"
        report = _json(members["report.json"])
        samples, decisions = parse_exports(members["observations.csv"], members["decisions.csv"], report)
        result.update(observations=48, hypothetical_decisions=48,
                      unique_exported_holdout_folds=12, scenarios_per_reused_fold=4)
        result["stages"]["exported_grid"] = "PASS"
        result["stages"]["structural_semantics"] = "PROVISIONAL_REFERENCE_ONLY"
        if reference_policy is None:
            result["validation_status"] = "HOLD_POLICY_REFERENCE_REQUIRED"
            result["reason_codes"].append("EXPLICIT_TIE_PRIORITY_ENCODING_STATE_AND_REPORT_LAYOUT_REQUIRED")
        else:
            result["policy_reference_canonical_sha256"] = _sha(dumps(reference_policy))
            summary, statistics = reconstruct(samples, decisions, reference_policy, report)
            result["arithmetic_summary"] = summary
            result["stages"]["arithmetic"] = "PASS"
            result["stages"]["profile_isolation"] = "PASS"
            matched = validate_report_statistics(report, statistics, reference_policy)
            result["stages"]["report_statistics"] = "PASS"
            result["arithmetic_summary"]["matched_report_statistics"] = matched
            result["group_statistics"] = [
                {"profile": p, "scenario": s, **values}
                for (p, s), values in sorted(statistics["groups"].items())
            ]
            if summary["unresolved_final_ties"]:
                result["stages"]["placement_policy"] = "HOLD_FINAL_TIE_REFERENCE"
                result["validation_status"] = "HOLD_FINAL_TIE_REFERENCE"
                result["reason_codes"].append("ORIGINAL_FINAL_TIE_RULE_NOT_SUPPLIED")
            else:
                result["stages"]["placement_policy"] = "PASS"
                result["validation_status"] = "OUTPUT_VALIDATION_COMPLETE"
    except ArtifactError as error:
        result["validation_status"] = "HOLD_ARTIFACT_VALIDATION"
        result["reason_codes"].append(str(error))
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError):
        result["validation_status"] = "HOLD_ARTIFACT_VALIDATION"
        result["reason_codes"].append("EXPORT_OR_REFERENCE_CONTRACT_MALFORMED")
    except OSError:
        result["validation_status"] = "HOLD_ARTIFACT_VALIDATION"
        result["reason_codes"].append("SOURCE_FILE_ACCESS_FAILED")
    result["reason_codes"] = sorted(set(result["reason_codes"] + [
        "SOURCE_FILES_AND_EVENT_CHAIN_NOT_INDEPENDENTLY_VERIFIED",
        "HISTORICAL_PERMISSION_EVIDENCE_NOT_VERIFIED", "HUMAN_PROVENANCE_REVIEW_REQUIRED",
    ]))
    return result


def write_summary(source: Path, output_dir: Path, *, opt_in: bool = False, reference_policy: dict | None = None) -> dict:
    result = inspect_outputs(source, opt_in=opt_in, reference_policy=reference_policy)
    output_dir.mkdir(parents=True, exist_ok=False)
    payload = dumps(result) + b"\n"
    manifest = {
        "schema_version": VERSION, "derivation": "CONTROLLED_SUMMARY_REDACTION_V01",
        "source_zip_sha256": result["source_zip_sha256"],
        "source_member_sha256": result["source_member_sha256"],
        "policy_reference_canonical_sha256": result["policy_reference_canonical_sha256"],
        "files_sha256": {"validation.json": _sha(payload)},
        "source_authenticity": "NOT_VERIFIED",
    }
    for name, content in (("validation.json", payload), ("manifest.json", dumps(manifest) + b"\n")):
        with (output_dir / name).open("xb") as stream:
            stream.write(content)
        (output_dir / name).chmod(0o444)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-p0c1-output-inspection", action="store_true")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--policy-reference", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.allow_p0c1_output_inspection:
        print(json.dumps({"status": "OPT_IN_REQUIRED"}))
        return 3
    try:
        reference = _json(_read(args.policy_reference.parent, args.policy_reference.name)) if args.policy_reference else None
        result = write_summary(args.source, args.output_dir, opt_in=True, reference_policy=reference)
    except ArtifactError:
        print(json.dumps({"status": "HOLD_PROVENANCE", "reason_codes": ["POLICY_REFERENCE_UNAVAILABLE_OR_INVALID"]}))
        return 2
    except OSError:
        print(json.dumps({"status": "OUTPUT_REFUSED"}))
        return 4
    print(json.dumps(result, sort_keys=True))
    return 2  # Successful output-only validation still HOLDs provenance/permissions.


if __name__ == "__main__":
    raise SystemExit(main())
