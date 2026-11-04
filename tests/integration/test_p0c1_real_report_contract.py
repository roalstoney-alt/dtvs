"""Synthetic examples of the observed report layout, never operator rows."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from dtvs.common.canonical_json import dumps
from dtvs.scheduling.p0c1_output_inspector import inspect_outputs, write_summary
from dtvs.scheduling.p0c1_reference_replay import forecast
from tests.integration.test_p0c1_output_inspector import (
    DEC_FIELDS, OBS_FIELDS, PATHS, csv_bytes, make_contract_example,
)


class P0C1RealReportContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.source = Path(self.temporary.name) / "invented-export"
        self.source.mkdir()
        self.observations, self.decisions, self.report, self.reference = make_contract_example()
        self.reference["schema_version"] = "p0c1-output-reference-v0.2"
        self.reference["report_checks"] = []
        self.report.pop("test_groups")
        self.report["statistics"] = []
        for profile in ("OLD_WIFI", "NEW_WIFI"):
            for scenario in ("LOCAL_ALLOWED", "LOCAL_FORBIDDEN", "LOCAL_AND_RANGE_FORBIDDEN", "RELAY_ONLY"):
                rows = [r for r in self.decisions if r["profile"] == profile and r["scenario"] == scenario]
                counts = {path: sum(row["selected_path"] == path for row in rows) for path in PATHS}
                index = len(self.report["statistics"])
                self.report["statistics"].append({
                    "profile": profile, "scenario": scenario, "n": len(rows),
                    "mean_regret_pct": round(sum(float(row["regret_pct"]) for row in rows) / len(rows), 3),
                    "max_regret_pct": round(max(float(row["regret_pct"]) for row in rows), 3),
                    "selected_paths": {path: count for path, count in counts.items() if count},
                })
                for field, statistic in (("n", "decision_count"), ("mean_regret_pct", "mean_regret_pct"), ("max_regret_pct", "max_regret_pct"), ("selected_paths", "selected_counts")):
                    self.reference["report_checks"].append({"pointer": f"/statistics/{index}/{field}", "profile": profile, "scenario": scenario, "statistic": statistic, "decimals": 3 if "regret" in field else 0})
        self.reference["report_checks"].append({"pointer": "/max_regret_pct", "profile": None, "scenario": None, "statistic": "max_regret_pct", "decimals": 3})
        self.save()

    def save(self):
        files = {
            "report.json": json.dumps(self.report).encode(),
            "report.md": b"# Invented report layout test only\n",
            "observations.csv": csv_bytes(OBS_FIELDS, self.observations),
            "decisions.csv": csv_bytes(DEC_FIELDS, self.decisions),
        }
        files["manifest.json"] = json.dumps({"input_mode": "RAW_RUN_FILES", "files_sha256": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}).encode()
        for name, content in files.items():
            (self.source / name).write_bytes(content)

    def inspect(self):
        return inspect_outputs(self.source, opt_in=True, reference_policy=self.reference)

    def test_actual_statistic_names_and_sparse_counts_without_invented_elapsed_mean(self):
        result = self.inspect()
        self.assertEqual(result["validation_status"], "OUTPUT_VALIDATION_COMPLETE", result["reason_codes"])
        self.assertEqual(result["stages"]["report_statistics"], "PASS")
        self.assertEqual(result["arithmetic_summary"]["matched_report_statistics"], 33)
        self.assertFalse(any(check["statistic"] == "mean_actual_s" for check in self.reference["report_checks"]))

    def test_missing_tie_rule_does_not_prevent_independent_value_checks(self):
        self.reference["tie_priority"] = None
        before = dumps(self.reference)
        result = self.inspect()
        self.assertEqual(result["validation_status"], "HOLD_FINAL_TIE_REFERENCE")
        self.assertEqual(result["stages"]["arithmetic"], "PASS")
        self.assertEqual(result["stages"]["report_statistics"], "PASS")
        self.assertEqual(result["stages"]["placement_policy"], "HOLD_FINAL_TIE_REFERENCE")
        summary = result["arithmetic_summary"]
        self.assertEqual(summary["matched_selections"], 45)
        self.assertEqual(summary["unresolved_final_ties"], 3)
        for name in ("matched_predictions", "matched_actuals", "matched_oracles", "matched_regrets", "matched_payloads"):
            self.assertEqual(summary[name], 48)
        self.assertEqual(before, dumps(self.reference))
        self.assertEqual(result["permissions_status"], "HOLD_ELIGIBILITY_UNKNOWN")

    def test_unknown_priority_returns_no_choice_for_equal_payload(self):
        training = {PATHS[1]: [{"elapsed_s": 100, "payload_bytes": 1000}] * 2, PATHS[3]: [{"elapsed_s": 102, "payload_bytes": 1000}] * 2}
        selected, predictions = forecast(training, set(training), None)
        self.assertIsNone(selected)
        self.assertEqual(set(predictions), set(training))

    def test_known_unique_choice_does_not_require_unused_priority(self):
        training = {PATHS[1]: [{"elapsed_s": 100, "payload_bytes": 1000}] * 2, PATHS[3]: [{"elapsed_s": 102, "payload_bytes": 100}] * 2}
        self.assertEqual(forecast(training, set(training), None)[0], PATHS[3])

    def test_operator_reference_priority_ignores_latency_inside_equal_payload_band(self):
        priority = [PATHS[1], PATHS[3], PATHS[2], PATHS[0]]
        for preferred, faster in zip(priority, priority[1:]):
            with self.subTest(preferred=preferred, faster=faster):
                training = {
                    preferred: [{"elapsed_s": 102, "payload_bytes": 1000}] * 2,
                    faster: [{"elapsed_s": 100, "payload_bytes": 1000}] * 2,
                }
                self.assertEqual(forecast(training, set(training), priority)[0], preferred)

    def test_unknown_tie_does_not_allow_a_nonminimal_payload_claim(self):
        self.reference["tie_priority"] = None
        row = next(row for row in self.decisions if row["profile"] == "OLD_WIFI" and row["query"] == "Q2" and row["scenario"] == "LOCAL_FORBIDDEN")
        row["selected_path"] = PATHS[0]
        self.save()
        self.assertIn("DECISION_MISRANKED", self.inspect()["reason_codes"])

    def test_oracle_is_still_checked_on_an_unresolved_tie(self):
        self.reference["tie_priority"] = None
        row = next(row for row in self.decisions if row["profile"] == "OLD_WIFI" and row["query"] == "Q2" and row["scenario"] == "LOCAL_FORBIDDEN")
        row["oracle_s"] = "1"
        self.save()
        self.assertIn("EXPORTED_ORACLE_S_MISMATCH", self.inspect()["reason_codes"])

    def test_sparse_count_validation_rejects_wrong_unknown_and_fractional_counts(self):
        original = copy.deepcopy(self.report["statistics"][0]["selected_paths"])
        for invalid in ({}, {"UNKNOWN": 6}, {PATHS[2]: 6.0}, {PATHS[2]: -1}):
            with self.subTest(invalid=invalid):
                self.report["statistics"][0]["selected_paths"] = invalid
                self.save()
                self.assertIn("REPORT_STATISTIC_MISMATCH", self.inspect()["reason_codes"])
        self.report["statistics"][0]["selected_paths"] = original

    def test_v02_allows_exactly_available_statistics_coverage(self):
        self.reference["report_checks"] = [check for check in self.reference["report_checks"] if check["statistic"] != "selected_counts"]
        self.assertEqual(len(self.reference["report_checks"]), 25)
        self.assertEqual(self.inspect()["validation_status"], "OUTPUT_VALIDATION_COMPLETE")

    def test_legacy_reference_contract_does_not_silently_relax(self):
        self.reference["schema_version"] = "p0c1-output-reference-v0.1"
        self.assertIn("REPORT_CHECK_COVERAGE_REQUIRED", self.inspect()["reason_codes"])
        self.reference["tie_priority"] = None
        self.assertIn("EXPLICIT_FINAL_TIE_PRIORITY_REQUIRED", self.inspect()["reason_codes"])

    def test_report_n_requires_an_exact_integer(self):
        self.report["statistics"][0]["n"] = 6.1
        self.save()
        self.assertIn("REPORT_STATISTIC_MISMATCH", self.inspect()["reason_codes"])

    def test_supplying_known_test_priority_resolves_only_the_test_example(self):
        self.reference["tie_priority"] = None
        self.assertEqual(self.inspect()["arithmetic_summary"]["unresolved_final_ties"], 3)
        self.reference["tie_priority"] = [PATHS[3], PATHS[1], PATHS[2], PATHS[0]]
        result = self.inspect()
        self.assertEqual(result["arithmetic_summary"]["matched_selections"], 48)
        self.assertEqual(result["arithmetic_summary"]["unresolved_final_ties"], 0)
        self.assertEqual(result["status"], "HOLD_PROVENANCE")

    def test_partial_result_is_deterministic_and_preserves_inputs(self):
        self.reference["tie_priority"] = None
        before = {p.name: p.read_bytes() for p in self.source.iterdir()}
        root = Path(self.temporary.name)
        a = write_summary(self.source, root / "first", opt_in=True, reference_policy=self.reference)
        b = write_summary(self.source, root / "second", opt_in=True, reference_policy=self.reference)
        self.assertEqual(dumps(a), dumps(b))
        self.assertEqual((root / "first/validation.json").read_bytes(), (root / "second/validation.json").read_bytes())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.source.iterdir()})
        self.assertTrue(all(value == 0 for value in a["audit"].values()))


if __name__ == "__main__":
    unittest.main()
