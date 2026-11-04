"""Invented artifact-contract examples, never historical permission evidence."""
from __future__ import annotations

import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from dtvs.common.canonical_json import dumps
from dtvs.scheduling.historical_import import inspect_sanitized_artifacts, main, write_inspection
from dtvs.scheduling.historical_routes import classify_route

ROOT = Path(__file__).resolve().parents[2]


def route_record(letter: str, profile: str = "test-old-profile") -> dict:
    # Test expectations are explicit, independent of the implementation table.
    facts = {
        "A": ("WORKER", ["SOURCE", "CENTRAL", "WORKER"], "FULL_OBJECT"),
        "B": ("WORKER", ["SOURCE", "WORKER"], "FULL_OBJECT"),
        "C": ("SOURCE", ["SOURCE"], "IN_PLACE"),
        "D": ("WORKER", ["SOURCE", "WORKER"], "BYTE_RANGE_STREAM"),
    }
    site, path, access = facts[letter]
    return {
        "route_namespace": "P0C1_LAN_V01", "environment_profile_id": profile,
        "source_route_id": letter, "execution_site": site,
        "input_path": path, "input_access": access,
    }


class P0C1HistoricalImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / "sanitized-test-only"
        self.source.mkdir()
        self.report = {
            "status": "OFFLINE_REPLAY_ONLY", "observations": 8, "holdout_decisions": 8,
            "test_fixture": "INVENTED_ARTIFACT_CONTRACT_NOT_HISTORICAL_EVIDENCE",
            "route_semantics": [route_record(letter, profile) for profile in ("test-old-profile", "test-new-profile") for letter in "ABCD"],
        }
        (self.source / "report.md").write_text("# Test only\nInvented artifact contract; no historical evidence.\n")
        lines = ["environment_profile_id,task_id,repeat_id,source_route_id"]
        lines += [f"{profile},test-task,test-repeat-{letter},{letter}" for profile in ("test-old-profile", "test-new-profile") for letter in "ABCD"]
        (self.source / "decisions.csv").write_text("\n".join(lines) + "\n")
        self.save_report()

    def save_report(self):
        (self.source / "report.json").write_text(json.dumps(self.report) + "\n")
        self.refresh_manifest()

    def refresh_manifest(self):
        # This is an untrusted, test-only RAW_RUN_FILES claim, not raw proof.
        manifest = {"input_mode": "RAW_RUN_FILES", "files_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(self.source.iterdir()) if p.name in {"report.md", "report.json", "decisions.csv"}
        }}
        (self.source / "manifest.json").write_text(json.dumps(manifest) + "\n")

    def inspect(self):
        return inspect_sanitized_artifacts(self.source, opt_in=True)

    def test_explicit_historical_semantics_map_all_four_routes(self):
        expected = {"A": "CENTRAL_RELAY", "B": "DIRECT_SOURCE", "C": "IN_SITU", "D": "STREAM_RANGE"}
        result = self.inspect()
        self.assertEqual(len(result["route_mappings"]), 8)
        for mapping in result["route_mappings"]:
            self.assertEqual(mapping["canonical_route"], expected[mapping["source_route_label"]])
            self.assertEqual(mapping["status"], "MAPPED_SEMANTICS_ONLY")
        self.assertEqual(len({m["environment_profile_sha256"] for m in result["route_mappings"]}), 2)

    def test_letters_alone_and_legacy_synthetic_modes_never_map(self):
        for letter in "ABCD":
            with self.subTest(letter=letter):
                record = {"route_namespace": "P0C1_LAN_V01", "source_route_id": letter}
                self.assertEqual(classify_route(record)["status"], "HOLD_SEMANTIC_MAPPING")
        for label, mode in (("A_LOCAL", "LOCAL"), ("B_DIRECT", "DIRECT"), ("C_RANGE", "RANGE"), ("D_REMOTE", "REMOTE")):
            with self.subTest(label=label):
                result = classify_route({"source_route_id": label, "mode": mode})
                self.assertIsNone(result["canonical_route"])
                self.assertEqual(result["status"], "HOLD_SEMANTIC_MAPPING")

    def test_matching_canonical_name_without_structural_facts_is_insufficient(self):
        result = classify_route({"route_namespace": "P0C1_LAN_V01", "source_route_id": "A", "declared_canonical_route": "CENTRAL_RELAY"})
        self.assertIsNone(result["canonical_route"])

    def test_semantics_drive_mapping_for_nonletter_identifier(self):
        record = route_record("C")
        record["source_route_id"] = "opaque-route-record-17"
        result = classify_route(record)
        self.assertEqual(result["canonical_route"], "IN_SITU")
        self.assertIsNone(result["source_route_label"])
        self.assertNotIn(record["source_route_id"], json.dumps(result))

    def test_historical_c_cannot_be_silently_interpreted_as_stream_range(self):
        record = route_record("D")
        record["source_route_id"] = "C"
        result = classify_route(record)
        self.assertEqual(result["reason_codes"], ["HISTORICAL_LETTER_SEMANTICS_CONFLICT"])
        self.assertIsNone(result["canonical_route"])

    def test_wrong_namespace_or_conflicting_declaration_holds(self):
        record = route_record("A")
        record["route_namespace"] = "SYNTHETIC_FIXTURE"
        self.assertEqual(classify_route(record)["status"], "HOLD_SEMANTIC_MAPPING")
        record["route_namespace"] = "P0C1_LAN_V01"
        record["declared_canonical_route"] = "DIRECT_SOURCE"
        self.assertEqual(classify_route(record)["reason_codes"], ["DECLARED_CANONICAL_ROUTE_CONFLICT"])

    def test_valid_output_hashes_still_hold_provenance_permissions_and_acceptance(self):
        result = self.inspect()
        self.assertEqual(result["artifact_validation"], "LISTED_OUTPUT_HASHES_MATCH")
        self.assertEqual(result["status"], "HOLD_PROVENANCE")
        self.assertEqual(result["claimed_source_input_mode"], "RAW_RUN_FILES")
        self.assertEqual(result["permissions_status"], "HOLD_ELIGIBILITY_UNKNOWN")
        self.assertEqual(result["historical_performance_acceptance"], "HOLD")
        self.assertEqual(result["raw_content_authenticity"], "NOT_VERIFIED")
        self.assertEqual(result["csv_rows_validated"], 8)
        self.assertIsNone(result["selected_route"])
        self.assertIsNone(result["historical_regret"])
        self.assertTrue(all(count == 0 for count in result["audit"].values()))
        for forbidden in ("tasks", "authorization", "signature", "candidates", "decisions"):
            self.assertNotIn(forbidden, result)

    def test_import_is_opt_in_before_any_file_reads_or_output_creation(self):
        out = Path(self.directory.name) / "output"
        with patch("dtvs.scheduling.historical_import._read", side_effect=AssertionError("must not read")):
            with self.assertRaisesRegex(PermissionError, "OPT_IN_REQUIRED"):
                inspect_sanitized_artifacts(self.source)
            with self.assertRaises(PermissionError):
                write_inspection(self.source, out, opt_in=False)
        self.assertFalse(out.exists())

    def test_report_permission_acceptance_and_signature_claims_are_not_promoted(self):
        self.report.update(permissions_verified=True, historical_performance_acceptance="APPROVE_OFFLINE_INTEGRATION", signature="untrusted-test-claim")
        self.save_report()
        result = self.inspect()
        self.assertEqual(result["permissions_status"], "HOLD_ELIGIBILITY_UNKNOWN")
        self.assertEqual(result["historical_performance_acceptance"], "HOLD")
        self.assertEqual(result["audit"]["signatures_created"], 0)
        self.assertEqual(result["audit"]["permission_assertions_created"], 0)

    def test_absent_operator_artifacts_return_hold_without_search_or_fallback(self):
        result = inspect_sanitized_artifacts(Path(self.directory.name) / "not-supplied", opt_in=True)
        self.assertEqual(result["status"], "HOLD_ARTIFACT_VALIDATION")
        self.assertIn("ARTIFACT_UNAVAILABLE_OR_SYMLINK", result["reason_codes"])
        self.assertIsNone(result["reported_counts"])
        self.assertEqual(result["route_mappings"], [])

    def test_missing_semantics_and_optional_csv_are_explicit_holds(self):
        del self.report["route_semantics"]
        (self.source / "decisions.csv").unlink()
        self.save_report()
        result = self.inspect()
        self.assertEqual(result["status"], "HOLD_PROVENANCE")
        self.assertIn("ROUTE_SEMANTICS_NOT_SUPPLIED", result["reason_codes"])
        self.assertIn("DECISIONS_CSV_NOT_SUPPLIED", result["reason_codes"])
        self.assertEqual(result["route_mappings"], [])

    def test_conflicting_semantics_remain_hold_when_csv_ids_match(self):
        record = self.report["route_semantics"][2]
        record.update(execution_site="WORKER", input_path=["SOURCE", "WORKER"], input_access="BYTE_RANGE_STREAM")
        self.save_report()
        result = self.inspect()
        self.assertIn("HOLD_SEMANTIC_MAPPING", result["reason_codes"])
        self.assertIsNone(result["route_mappings"][2]["canonical_route"])
        self.assertEqual(result["status"], "HOLD_PROVENANCE")

    def test_artifact_hash_mismatch_is_not_historical_evidence(self):
        (self.source / "report.json").write_text('{}')
        result = self.inspect()
        self.assertEqual(result["status"], "HOLD_ARTIFACT_VALIDATION")
        self.assertIn("ARTIFACT_HASH_MISMATCH", result["reason_codes"])

    def test_unmanifested_decisions_are_never_imported(self):
        manifest = json.loads((self.source / "manifest.json").read_text())
        del manifest["files_sha256"]["decisions.csv"]
        (self.source / "manifest.json").write_text(json.dumps(manifest))
        result = self.inspect()
        self.assertIsNone(result["csv_rows_validated"])
        self.assertIn("UNMANIFESTED_ARTIFACT_NOT_IMPORTED", result["reason_codes"])

    def test_manifest_paths_unknown_files_and_symlinks_are_refused(self):
        original = (self.source / "manifest.json").read_bytes()
        for name in ("../outside.json", "nested/report.json", "raw-events.jsonl"):
            with self.subTest(name=name):
                manifest = json.loads(original)
                manifest["files_sha256"][name] = "0" * 64
                (self.source / "manifest.json").write_text(json.dumps(manifest))
                self.assertIn("SANITIZED_MANIFEST_FILE_SET_UNSUPPORTED", self.inspect()["reason_codes"])
        (self.source / "manifest.json").write_bytes(original)
        target = Path(self.directory.name) / "outside-report.json"
        (self.source / "report.json").rename(target)
        (self.source / "report.json").symlink_to(target)
        self.assertIn("ARTIFACT_UNAVAILABLE_OR_SYMLINK", self.inspect()["reason_codes"])

    def test_duplicate_json_keys_and_nonfinite_fields_hold(self):
        for content in (b'{"status":1,"status":2}', b'{"unused":NaN}', b'{"unused":1e999}', b'{"unused":"\\ud800"}'):
            with self.subTest(content=content):
                (self.source / "report.json").write_bytes(content)
                self.refresh_manifest()
                self.assertEqual(self.inspect()["status"], "HOLD_ARTIFACT_VALIDATION")

    def test_unknown_report_layout_and_input_mode_hold(self):
        self.report["status"] = "ACCEPTED"
        self.save_report()
        self.assertIn("OFFLINE_REPORT_STATUS_REQUIRED", self.inspect()["reason_codes"])
        manifest = json.loads((self.source / "manifest.json").read_text())
        manifest["input_mode"] = "SYNTHETIC_FIXTURE"
        (self.source / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn("RAW_RUN_FILES_CLAIM_REQUIRED", self.inspect()["reason_codes"])

    def test_csv_count_duplicates_unknown_route_and_unknown_columns_hold(self):
        original = (self.source / "decisions.csv").read_text()
        lines = original.splitlines()
        cases = (
            ("\n".join(lines[:-1]) + "\n", "DECISION_COUNT_MISMATCH"),
            (original + lines[1] + "\n", "DUPLICATE_DECISION_ROW"),
            (original.replace("test-repeat-A,A", "test-repeat-A,unknown-route"), "DECISION_ROUTE_SEMANTICS_UNAVAILABLE"),
            ("route,time\nA,1\n", "DECISIONS_CSV_LAYOUT_UNSUPPORTED"),
        )
        for content, reason in cases:
            with self.subTest(reason=reason):
                (self.source / "decisions.csv").write_text(content)
                self.refresh_manifest()
                self.assertIn(reason, self.inspect()["reason_codes"])

    def test_duplicate_route_metadata_is_ambiguous(self):
        self.report["route_semantics"].append(copy.deepcopy(self.report["route_semantics"][0]))
        self.save_report()
        self.assertIn("DUPLICATE_ROUTE_SEMANTICS", self.inspect()["reason_codes"])

    def test_inspection_is_deterministic_offline_and_does_not_overwrite_inputs(self):
        before = {p.name: p.read_bytes() for p in self.source.iterdir()}
        first, second = Path(self.directory.name) / "first", Path(self.directory.name) / "second"
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            one = write_inspection(self.source, first, opt_in=True)
            two = write_inspection(self.source, second, opt_in=True)
        self.assertEqual(dumps(one), dumps(two))
        for name in ("validation.json", "manifest.json"):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
        manifest = json.loads((first / "manifest.json").read_text())
        self.assertEqual(hashlib.sha256((first / "validation.json").read_bytes()).hexdigest(), manifest["files_sha256"]["validation.json"])
        with self.assertRaises(FileExistsError):
            write_inspection(self.source, first, opt_in=True)
        with self.assertRaises(FileExistsError):
            write_inspection(self.source, self.source, opt_in=True)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.source.iterdir()})

    def test_importer_does_not_create_a_synthetic_replay_dataset(self):
        result = self.inspect()
        self.assertNotIn("profiles", result)
        self.assertNotIn("events", result)
        self.assertNotIn("fixture_sha256", result)
        import ast
        for name in ("historical_import.py", "historical_routes.py"):
            for node in ast.walk(ast.parse((ROOT / "dtvs/scheduling" / name).read_text())):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn(node.module, {"dtvs.contracts.signing", "dtvs.scheduling.replay", "dtvs.scheduling.placement_policy"})

    def test_cli_exit_codes_distinguish_opt_in_hold_and_output_refusal(self):
        output = Path(self.directory.name) / "cli-output"
        command = [sys.executable, "-m", "dtvs.scheduling.historical_import", "--input-dir", str(self.source), "--output-dir", str(output)]
        no_opt_in = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(no_opt_in.returncode, 3, no_opt_in.stderr)
        self.assertFalse(output.exists())
        held = subprocess.run(command + ["--allow-sanitized-p0c1-import"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(held.returncode, 2, held.stderr)
        self.assertEqual(json.loads(held.stdout)["status"], "HOLD_PROVENANCE")
        refused = subprocess.run(command + ["--allow-sanitized-p0c1-import"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(refused.returncode, 4, refused.stderr)

    def test_output_permission_error_is_not_misreported_as_missing_opt_in(self):
        stdout = io.StringIO()
        with patch("dtvs.scheduling.historical_import.write_inspection", side_effect=PermissionError), redirect_stdout(stdout):
            code = main(["--allow-sanitized-p0c1-import", "--input-dir", str(self.source), "--output-dir", str(Path(self.directory.name) / "denied")])
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "OUTPUT_REFUSED")


if __name__ == "__main__":
    unittest.main()
