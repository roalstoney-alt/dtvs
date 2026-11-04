"""Invented five-file exports. No original operator data or permission evidence."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from dtvs.common.canonical_json import dumps
from dtvs.scheduling.p0c1_output_inspector import inspect_outputs, write_summary
from dtvs.scheduling.p0c1_reference_replay import forecast, parse_exports

ROOT = Path(__file__).resolve().parents[2]
PATHS = ("A_CENTRAL_RELAY", "B_DIRECT_SOURCE", "C_IN_SITU", "D_STREAM_RANGE")
OBS_FIELDS = ("profile", "query", "path", "repeat", "status", "elapsed_s", "payload_bytes")
DEC_FIELDS = ("profile", "scenario", "query", "heldout_repeat", "eligible_paths", "selected_path", "predicted_s", "actual_s", "oracle_s", "regret_pct", "payload_bytes", "decision_state")
FEASIBLE = {
    "LOCAL_ALLOWED": PATHS,
    "LOCAL_FORBIDDEN": (PATHS[0], PATHS[1], PATHS[3]),
    "LOCAL_AND_RANGE_FORBIDDEN": (PATHS[0], PATHS[1]),
    "RELAY_ONLY": (PATHS[0],),
}


def csv_bytes(fields, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def make_contract_example():
    """Expected choices are specified manually, not by the production ranker."""
    observations, decisions, sample = [], [], {}
    for profile in ("OLD_WIFI", "NEW_WIFI"):
        times = [[100] * 3, [100] * 3, [10] * 3, [102] * 3] if profile == "OLD_WIFI" else [[95] * 3, [90, 90, 98], [10] * 3, [100] * 3]
        for query in ("Q1", "Q2"):
            scale = 1 if query == "Q1" else 2
            payloads = [2000, 1000, 8, 100 if query == "Q1" else 1000]
            for path, elapsed, payload in zip(PATHS, times, payloads):
                for repeat in (1, 2, 3):
                    sample[profile, query, path, repeat] = (elapsed[repeat - 1] * scale, payload)
                    observations.append(dict(zip(OBS_FIELDS, (profile, query, path, str(repeat), "ACCEPTED", f"{elapsed[repeat - 1] * scale:.4f}", str(payload)))))
            for scenario, feasible in FEASIBLE.items():
                chosen = PATHS[2] if scenario == "LOCAL_ALLOWED" else PATHS[0] if scenario == "RELAY_ONLY" else PATHS[3] if scenario == "LOCAL_FORBIDDEN" and profile == "OLD_WIFI" else PATHS[1]
                for heldout in (1, 2, 3):
                    # Two-value median is an average; no production function called.
                    prediction = sum(sample[profile, query, chosen, k][0] for k in (1, 2, 3) if k != heldout) / 2
                    actual, payload = sample[profile, query, chosen, heldout]
                    oracle = min(sample[profile, query, path, heldout][0] for path in feasible)
                    regret = (actual / oracle - 1) * 100
                    decisions.append(dict(zip(DEC_FIELDS, (profile, scenario, query, str(heldout), json.dumps(feasible), chosen, f"{prediction:.4f}", f"{actual:.4f}", f"{oracle:.4f}", f"{regret:.6f}", str(payload), "HYPOTHETICAL_TEST_ONLY"))))
    policy = {"test_only": True, "estimator": "MEDIAN_TWO_OTHER_REPEATS", "latency_tolerance_pct": 3}
    reference = {
        "schema_version": "p0c1-output-reference-v0.1", "route_namespace": "P0C1_LAN_V01",
        "source_reference_sha256": hashlib.sha256(b"invented reference for contract tests only").hexdigest(),
        "tie_priority": [PATHS[3], PATHS[1], PATHS[2], PATHS[0]],
        "eligible_paths_encoding": "JSON_ARRAY", "decision_state": "HYPOTHETICAL_TEST_ONLY",
        "expected_report_policy": policy, "csv_regret_decimals": 6, "report_checks": [],
    }
    report = {
        "status": "OFFLINE_REPLAY_ONLY", "observations": 48, "holdout_decisions": 48,
        "policy": policy, "test_groups": [],
        "source_provenance": {"private_location": "PRIVATE_SENTINEL_TEST_ONLY", "credential_claim": "NOT_A_REAL_TOKEN"},
        "max_regret_pct": round(max(float(row["regret_pct"]) for row in decisions), 3),
    }
    for profile in ("OLD_WIFI", "NEW_WIFI"):
        for scenario in FEASIBLE:
            rows = [row for row in decisions if row["profile"] == profile and row["scenario"] == scenario]
            group = {
                "decision_count": len(rows),
                "mean_actual_s": round(sum(float(row["actual_s"]) for row in rows) / len(rows), 4),
                "mean_regret_pct": round(sum(float(row["regret_pct"]) for row in rows) / len(rows), 3),
                "max_regret_pct": round(max(float(row["regret_pct"]) for row in rows), 3),
            }
            index = len(report["test_groups"])
            report["test_groups"].append(group)
            for name in group:
                reference["report_checks"].append({"pointer": f"/test_groups/{index}/{name}", "profile": profile, "scenario": scenario, "statistic": name, "decimals": 0 if name == "decision_count" else 4 if name == "mean_actual_s" else 3})
    reference["report_checks"].append({"pointer": "/max_regret_pct", "profile": None, "scenario": None, "statistic": "max_regret_pct", "decimals": 3})
    return observations, decisions, report, reference


class P0C1OutputInspectorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / "invented-export"
        self.folder.mkdir()
        self.observations, self.decisions, self.report, self.reference = make_contract_example()
        self.save()

    def save(self):
        (self.folder / "observations.csv").write_bytes(csv_bytes(OBS_FIELDS, self.observations))
        (self.folder / "decisions.csv").write_bytes(csv_bytes(DEC_FIELDS, self.decisions))
        (self.folder / "report.json").write_text(json.dumps(self.report))
        (self.folder / "report.md").write_text("# Invented contract test\nNot operator evidence.\n")
        self.refresh_hashes()

    def refresh_hashes(self):
        manifest = {"input_mode": "RAW_RUN_FILES", "files_sha256": {name: hashlib.sha256((self.folder / name).read_bytes()).hexdigest() for name in ("report.json", "report.md", "observations.csv", "decisions.csv")}}
        (self.folder / "manifest.json").write_text(json.dumps(manifest))

    def pack(self):
        path = Path(self.temporary.name) / "outputs.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
            for name in ("manifest.json", "report.json", "report.md", "observations.csv", "decisions.csv"):
                archive.writestr(name, (self.folder / name).read_bytes())
        return path

    def inspect(self, source=None, reference=True):
        return inspect_outputs(source or self.folder, opt_in=True, reference_policy=self.reference if reference else None)

    def assert_hold_reason(self, reason):
        result = self.inspect()
        self.assertEqual(result["status"], "HOLD_PROVENANCE")
        self.assertIn(reason, result["reason_codes"])
        self.assertEqual(result["permissions_status"], "HOLD_ELIGIBILITY_UNKNOWN")

    def test_complete_five_file_contract_and_all_48_decisions(self):
        result = self.inspect()
        self.assertEqual(result["validation_status"], "OUTPUT_VALIDATION_COMPLETE", result["reason_codes"])
        self.assertEqual(result["stages"]["internal_hash_verification"], "PASS_SELF_CONTAINED")
        for name in ("arithmetic", "profile_isolation", "report_statistics", "exported_grid"):
            self.assertEqual(result["stages"][name], "PASS")
        self.assertEqual(result["stages"]["structural_semantics"], "PROVISIONAL_REFERENCE_ONLY")
        self.assertEqual(result["observations"], 48)
        self.assertEqual(result["hypothetical_decisions"], 48)
        self.assertEqual(result["unique_exported_holdout_folds"], 12)
        self.assertEqual(result["scenarios_per_reused_fold"], 4)
        self.assertEqual(result["arithmetic_summary"]["matched_report_statistics"], 33)
        self.assertAlmostEqual(result["arithmetic_summary"]["max_regret_pct"], (98 / 95 - 1) * 100)

    def test_zip_and_extracted_directory_agree_without_extracting_archive(self):
        archive = self.pack()
        before = archive.read_bytes()
        result = self.inspect(archive)
        self.assertEqual(result["validation_status"], "OUTPUT_VALIDATION_COMPLETE")
        self.assertEqual(result["arithmetic_summary"], self.inspect()["arithmetic_summary"])
        self.assertEqual(before, archive.read_bytes())

    def test_no_opt_in_means_no_reads_no_output(self):
        output = Path(self.temporary.name) / "not-created"
        with patch("dtvs.scheduling.p0c1_output_inspector.load_members", side_effect=AssertionError("must not read")):
            with self.assertRaises(PermissionError):
                write_summary(self.folder, output)
        self.assertFalse(output.exists())

    def test_final_priority_and_report_layout_are_not_guessed_from_decisions(self):
        result = self.inspect(reference=False)
        self.assertEqual(result["validation_status"], "HOLD_POLICY_REFERENCE_REQUIRED")
        self.assertEqual(result["stages"]["internal_hash_verification"], "PASS_SELF_CONTAINED")
        self.assertEqual(result["stages"]["arithmetic"], "NOT_RUN")

    def test_lower_payload_within_three_percent_beats_faster_route(self):
        training = {PATHS[1]: [{"elapsed_s": 100, "payload_bytes": 1000}] * 2, PATHS[3]: [{"elapsed_s": 102, "payload_bytes": 100}] * 2}
        selected, predictions = forecast(training, set(training), self.reference["tie_priority"])
        self.assertEqual(selected, PATHS[3])
        self.assertGreater(predictions[selected], predictions[PATHS[1]])

    def test_three_percent_boundary_is_inclusive_and_outside_is_excluded(self):
        training = {PATHS[1]: [{"elapsed_s": 100, "payload_bytes": 1000}] * 2, PATHS[3]: [{"elapsed_s": 103, "payload_bytes": 100}] * 2}
        self.assertEqual(forecast(training, set(training), self.reference["tie_priority"])[0], PATHS[3])
        training[PATHS[3]] = [{"elapsed_s": 103.0001, "payload_bytes": 100}] * 2
        self.assertEqual(forecast(training, set(training), self.reference["tie_priority"])[0], PATHS[1])

    def test_explicit_priority_breaks_equal_payload_not_alphabetical_or_fastest(self):
        self.reference["tie_priority"] = [PATHS[1], PATHS[3], PATHS[2], PATHS[0]]
        self.assert_hold_reason("DECISION_MISRANKED")

    def test_altered_single_byte_fails_exact_hash(self):
        with (self.folder / "report.md").open("ab") as stream:
            stream.write(b"x")
        self.assert_hold_reason("OUTPUT_MEMBER_HASH_MISMATCH")

    def test_missing_observations_is_refused(self):
        (self.folder / "observations.csv").unlink()
        self.assert_hold_reason("ARTIFACT_UNAVAILABLE_OR_SYMLINK")

    def test_missing_one_sample_cannot_pass_count_or_grid(self):
        self.observations.pop()
        self.save()
        self.assert_hold_reason("CSV_CARDINALITY_INVALID")

    def test_duplicate_observation_replacing_a_sample_is_refused(self):
        self.observations[-1] = copy.deepcopy(self.observations[0])
        self.save()
        self.assert_hold_reason("DUPLICATE_OBSERVATION")

    def test_duplicate_hypothetical_decision_is_refused(self):
        self.decisions[-1] = copy.deepcopy(self.decisions[0])
        self.save()
        self.assert_hold_reason("DUPLICATE_DECISION")

    def test_cross_profile_prediction_is_rejected(self):
        row = next(row for row in self.decisions if row["profile"] == "NEW_WIFI" and row["scenario"] == "LOCAL_FORBIDDEN")
        row["predicted_s"] = "102.0000"  # Value belongs to the other profile.
        self.save()
        self.assert_hold_reason("EXPORTED_PREDICTED_S_MISMATCH")

    def test_profile_leakage_in_observation_grid_is_rejected(self):
        self.observations[0]["profile"] = "NEW_WIFI"
        self.save()
        self.assert_hold_reason("DUPLICATE_OBSERVATION")

    def test_selected_route_misranking_is_rejected(self):
        self.decisions[0]["selected_path"] = PATHS[0]
        self.save()
        self.assert_hold_reason("DECISION_MISRANKED")

    def test_wrong_oracle_is_rejected(self):
        self.decisions[0]["oracle_s"] = "1.0000"
        self.save()
        self.assert_hold_reason("EXPORTED_ORACLE_S_MISMATCH")

    def test_wrong_actual_and_regret_are_rejected(self):
        for name, reason in (("actual_s", "EXPORTED_ACTUAL_S_MISMATCH"), ("regret_pct", "EXPORTED_REGRET_PCT_MISMATCH")):
            with self.subTest(name=name):
                original = self.decisions[0][name]
                self.decisions[0][name] = "1000.0000"
                self.save()
                self.assert_hold_reason(reason)
                self.decisions[0][name] = original

    def test_wrong_decision_or_observation_payload_is_rejected(self):
        self.decisions[0]["payload_bytes"] = "999"
        self.save()
        self.assert_hold_reason("DECISION_PAYLOAD_MISMATCH")
        self.decisions[0]["payload_bytes"] = "8"
        self.observations[0]["payload_bytes"] = "999"
        self.save()
        self.assert_hold_reason("PAYLOAD_NOT_CONSTANT_WITHIN_ROUTE")

    def test_hypothetical_feasible_set_mismatch_is_rejected(self):
        self.decisions[0]["eligible_paths"] = json.dumps([PATHS[0]])
        self.save()
        self.assert_hold_reason("HYPOTHETICAL_FEASIBLE_SET_MISMATCH")

    def test_forged_permission_flags_cannot_discharge_holds(self):
        self.report.update(permissions_verified=True, allow_dispatch=True, external_anchor_verified=True)
        self.save()
        result = self.inspect()
        self.assertEqual(result["validation_status"], "OUTPUT_VALIDATION_COMPLETE")
        self.assertEqual(result["status"], "HOLD_PROVENANCE")
        self.assertEqual(result["historical_permissions"], "HOLD")
        self.assertEqual(result["historical_performance_acceptance"], "HOLD")
        self.assertEqual(result["external_source_authenticity"], "NOT_VERIFIED")

    def test_no_raw_paths_claims_rows_or_tokens_are_echoed(self):
        raw = dumps(self.inspect()).decode()
        self.assertNotIn("PRIVATE_SENTINEL_TEST_ONLY", raw)
        self.assertNotIn("NOT_A_REAL_TOKEN", raw)
        self.assertNotIn("source_provenance", raw)
        self.assertNotIn("heldout_repeat", raw)

    def test_name_semantic_conflict_and_synthetic_labels_are_not_aliases(self):
        for wrong in ("C_STREAM_RANGE", "A_LOCAL", "C_RANGE", "D_REMOTE"):
            with self.subTest(wrong=wrong):
                self.observations[0]["path"] = wrong
                self.save()
                self.assert_hold_reason("PROFILE_QUERY_OR_ROUTE_SEMANTICS_INVALID")

    def test_csv_schema_drift_is_refused_without_guessing(self):
        content = (self.folder / "decisions.csv").read_bytes().replace(b"heldout_repeat", b"repeat", 1)
        (self.folder / "decisions.csv").write_bytes(content)
        self.refresh_hashes()
        self.assert_hold_reason("CSV_SCHEMA_DRIFT")

    def test_nonfinite_and_malformed_numeric_records_are_refused(self):
        for value in ("nan", "inf", "-1", "1e999", "not-a-number"):
            with self.subTest(value=value):
                self.observations[0]["elapsed_s"] = value
                self.save()
                self.assert_hold_reason("CSV_NUMERIC_VALUE_INVALID")

    def test_report_group_statistics_and_rounding_are_verified(self):
        self.report["test_groups"][0]["mean_actual_s"] += 1
        self.save()
        self.assert_hold_reason("REPORT_STATISTIC_MISMATCH")

    def test_fractional_group_count_is_not_accepted_as_rounded_integer(self):
        self.report["test_groups"][0]["decision_count"] = 6.4
        self.save()
        self.assert_hold_reason("REPORT_STATISTIC_MISMATCH")

    def test_unknown_report_layout_is_not_inferred(self):
        self.reference["report_checks"][0]["pointer"] = "/not-present/decision_count"
        self.assert_hold_reason("REPORT_STATISTICS_LAYOUT_MISMATCH")

    def test_unreported_final_priority_or_incomplete_report_checks_hold(self):
        del self.reference["tie_priority"]
        self.assert_hold_reason("POLICY_REFERENCE_SCHEMA_INVALID")

    def test_report_counts_status_and_policy_must_match(self):
        self.report["observations"] = 49
        self.save()
        self.assert_hold_reason("REPORT_CARDINALITY_INVALID")
        self.report["observations"] = 48
        self.report["policy"] = {"different_estimator": "mean"}
        self.save()
        self.assert_hold_reason("REPORT_POLICY_REFERENCE_MISMATCH")

    def test_report_policy_boolean_is_not_equal_to_integer_assertion(self):
        self.reference["expected_report_policy"] = copy.deepcopy(self.reference["expected_report_policy"])
        self.report["policy"]["test_only"] = 1
        self.save()
        self.assert_hold_reason("REPORT_POLICY_REFERENCE_MISMATCH")

    def test_heldout_elapsed_does_not_enter_forecast(self):
        samples, unused = parse_exports((self.folder / "observations.csv").read_bytes(), (self.folder / "decisions.csv").read_bytes(), self.report)
        def training():
            return {path: [samples["OLD_WIFI", "Q1", path, k] for k in (1, 2, 3) if k != 3] for path in PATHS}
        before = forecast(training(), set(PATHS), self.reference["tie_priority"])
        for path in PATHS:
            samples["OLD_WIFI", "Q1", path, 3]["elapsed_s"] *= 1000
        self.assertEqual(before, forecast(training(), set(PATHS), self.reference["tie_priority"]))

    def test_quoted_worst_case_numbers_reproduce_only_the_supplied_ratio(self):
        # A two-number arithmetic check, not a revalidation of absent originals.
        self.assertAlmostEqual((19.5661 / 18.5280 - 1) * 100, 5.602871329879111)

    def test_archive_illegal_paths_duplicates_and_symlinks_are_refused(self):
        for variant in ("traversal", "duplicate", "symlink"):
            with self.subTest(variant=variant):
                path = Path(self.temporary.name) / (variant + ".zip")
                with zipfile.ZipFile(path, "w") as archive:
                    for name in ("manifest.json", "report.json", "report.md", "observations.csv", "decisions.csv"):
                        if name == "report.json" and variant == "traversal":
                            archive.writestr("../report.json", b"{}"); continue
                        if name == "report.json" and variant == "symlink":
                            info = zipfile.ZipInfo(name)
                            info.create_system = 3
                            info.external_attr = (stat.S_IFLNK | 0o777) << 16
                            archive.writestr(info, b"outside"); continue
                        archive.writestr(name, (self.folder / name).read_bytes())
                    if variant == "duplicate":
                        # A sixth entry is refused even before its content is read.
                        archive.writestr("nested/report.json", b"{}")
                self.assertEqual(self.inspect(path)["validation_status"], "HOLD_ARTIFACT_VALIDATION")

    def test_archive_crc_and_resource_limits_are_enforced(self):
        path = self.pack()
        data = path.read_bytes()
        marker = (self.folder / "report.md").read_bytes()
        path.write_bytes(data.replace(marker, b"X" + marker[1:], 1))
        self.assertIn("ARCHIVE_CRC_OR_FORMAT_INVALID", self.inspect(path)["reason_codes"])
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in ("manifest.json", "report.json", "report.md", "observations.csv", "decisions.csv"):
                archive.writestr(name, b"x" * (9 * 1024 * 1024) if name == "report.md" else (self.folder / name).read_bytes())
        self.assertIn("ARCHIVE_RESOURCE_LIMIT", self.inspect(path)["reason_codes"])

    def test_actual_duplicate_archive_member_is_refused(self):
        path = self.pack()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "a") as archive:
                archive.writestr("report.json", b"{}")
        self.assertIn("ARCHIVE_MEMBER_SET_OR_DUPLICATE_INVALID", self.inspect(path)["reason_codes"])

    def test_deflate_corruption_is_a_controlled_hold(self):
        import zlib
        with patch("zipfile.ZipExtFile.read", side_effect=zlib.error("invented decompression failure")):
            result = self.inspect(self.pack())
        self.assertIn("ARCHIVE_CRC_OR_FORMAT_INVALID", result["reason_codes"])

    def test_explicit_pipe_encoding_and_state_are_verified(self):
        for row in self.decisions:
            row["eligible_paths"] = "|".join(json.loads(row["eligible_paths"]))
        self.reference["eligible_paths_encoding"] = "PIPE_SEPARATED"
        self.save()
        self.assertEqual(self.inspect()["validation_status"], "OUTPUT_VALIDATION_COMPLETE")
        self.decisions[0]["decision_state"] = "DIFFERENT_STATE"
        self.save()
        self.assert_hold_reason("DECISION_STATE_REFERENCE_MISMATCH")

    def test_directory_symlink_is_refused(self):
        source = Path(self.temporary.name) / "linked"
        source.symlink_to(self.folder, target_is_directory=True)
        self.assertIn("SOURCE_UNAVAILABLE_OR_SYMLINK", self.inspect(source)["reason_codes"])

    def test_deterministic_twice_read_only_inputs_and_zero_external_actions(self):
        source = self.pack()
        before = source.read_bytes()
        outputs = [Path(self.temporary.name) / name for name in ("first", "second")]
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            one = write_summary(source, outputs[0], opt_in=True, reference_policy=self.reference)
            two = write_summary(source, outputs[1], opt_in=True, reference_policy=self.reference)
        self.assertEqual(dumps(one), dumps(two))
        self.assertEqual(before, source.read_bytes())
        self.assertTrue(all(count == 0 for count in one["audit"].values()))
        for name in ("validation.json", "manifest.json"):
            self.assertEqual((outputs[0] / name).read_bytes(), (outputs[1] / name).read_bytes())
        manifest = json.loads((outputs[0] / "manifest.json").read_text())
        self.assertEqual(hashlib.sha256((outputs[0] / "validation.json").read_bytes()).hexdigest(), manifest["files_sha256"]["validation.json"])
        with self.assertRaises(FileExistsError):
            write_summary(source, outputs[0], opt_in=True, reference_policy=self.reference)
        with self.assertRaises(FileExistsError):
            write_summary(source, self.folder, opt_in=True, reference_policy=self.reference)

    def test_cli_opt_in_hold_exit_and_no_source_data_echo(self):
        reference_path = Path(self.temporary.name) / "test-reference.json"
        reference_path.write_text(json.dumps(self.reference))
        command = [sys.executable, "-m", "dtvs.scheduling.p0c1_output_inspector", "--source", str(self.folder), "--output-dir", str(Path(self.temporary.name) / "cli"), "--policy-reference", str(reference_path)]
        no_opt_in = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(no_opt_in.returncode, 3)
        held = subprocess.run(command + ["--allow-p0c1-output-inspection"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(held.returncode, 2, held.stderr)
        self.assertEqual(json.loads(held.stdout)["validation_status"], "OUTPUT_VALIDATION_COMPLETE")
        self.assertNotIn("PRIVATE_SENTINEL_TEST_ONLY", held.stdout)


if __name__ == "__main__":
    unittest.main()
