from __future__ import annotations

import json
import unittest
from pathlib import Path

from dtvs.pilot import run_fixture_pilot

ROOT = Path(__file__).resolve().parents[2]


class Phase5FaultRecoveryTests(unittest.TestCase):
    def test_fixture_pilot_records_all_frozen_faults_and_recovers(self):
        out_root = ROOT / "runs" / "unit-phase5-a"
        summary = run_fixture_pilot(ROOT / "configs/metropolis_20m_v022.json", out_root)
        self.assertEqual(summary["task_count"], 20)
        self.assertEqual(summary["accepted_count"], 20)
        report_path = out_root / summary["run_id"] / "fault_injection_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        faulted = [item for item in report if item["expected_fault"]]
        self.assertEqual(len(faulted), 5)
        self.assertIn("IDEMPOTENT_UPLOAD_RETRY", {item["recovery_action"] for item in faulted})
        self.assertIn("REASSIGN_AFTER_BAD_HASH", {item["recovery_action"] for item in faulted})
        self.assertTrue((out_root / summary["run_id"] / "merge" / "final_output.fixture").exists())

    def test_accepted_tasks_are_not_reprocessed_by_normal_retry(self):
        out_root = ROOT / "runs" / "unit-phase5-b"
        summary = run_fixture_pilot(ROOT / "configs/metropolis_20m_v022.json", out_root)
        report = json.loads((out_root / summary["run_id"] / "fault_injection_report.json").read_text(encoding="utf-8"))
        accepted_attempts = {}
        for item in report:
            if item.get("final_state") == "ACCEPTED" and item.get("attempt_id"):
                accepted_attempts.setdefault(item["task_id"], 0)
                accepted_attempts[item["task_id"]] += 1
        self.assertTrue(all(count == 1 for count in accepted_attempts.values()))


if __name__ == "__main__":
    unittest.main()
