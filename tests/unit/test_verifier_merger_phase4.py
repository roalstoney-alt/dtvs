from __future__ import annotations

import json
import unittest
from pathlib import Path

from dtvs.coordinator.asset_freezer import freeze_asset
from dtvs.coordinator.task_compiler import compile_tasks
from dtvs.contracts.signing import generate_private_key
from dtvs.merger.accepted_index import build_accepted_index
from dtvs.merger.video_merge import merge_fixture
from dtvs.verifier.hidden_checks import deterministic_rerender_tasks
from dtvs.verifier.intake import list_attempt_dirs
from dtvs.verifier.verdict import make_verdict
from dtvs.worker.executor import execute_fixture
from dtvs.worker.local_qc import local_qc
from dtvs.worker.uploader import upload_attempt

ROOT = Path(__file__).resolve().parents[2]


class Phase4VerifierMergerTests(unittest.TestCase):
    def _compile(self, run_name: str):
        config = json.loads((ROOT / "configs/metropolis_20m_v022.json").read_text(encoding="utf-8"))
        asset = freeze_asset(config, ROOT)
        key = generate_private_key()
        compiled = compile_tasks(asset, config, private_key=key, key_id="pilot-local-001", output_dir=ROOT / "runs" / run_name / "bundles", hidden_secret=b"s")
        return config, compiled

    def test_missing_or_rejected_task_blocks_complete_delivery(self):
        config, compiled = self._compile("unit-phase4-block")
        cloud = ROOT / "runs" / "unit-phase4-block" / "simulated_cloud" / "inbox"
        task = compiled["tasks"][0]
        bundle = json.loads(Path(task["bundle_path"]).read_text(encoding="utf-8"))
        attempt = execute_fixture(bundle, ROOT / "runs" / "unit-phase4-block" / "worker" / "A001", attempt_id="A001", frame_count_delta=-1)
        qc = local_qc(bundle, attempt)
        upload_attempt(attempt, qc, cloud)
        for attempt_dir in list_attempt_dirs(cloud):
            make_verdict(attempt_dir, compiled["hidden_check_summary"])
        index = build_accepted_index(list_attempt_dirs(cloud), compiled["tasks"])
        delivery = merge_fixture(index, ROOT / "runs" / "unit-phase4-block" / "merge", segment_start=config["segment_start_frame"], segment_end=config["segment_end_frame_exclusive"])
        self.assertFalse(index["complete"])
        self.assertEqual(delivery["state"], "INCOMPLETE_DIAGNOSTIC_ONLY")

    def test_all_accepted_fixture_tasks_merge(self):
        config, compiled = self._compile("unit-phase4-merge")
        cloud = ROOT / "runs" / "unit-phase4-merge" / "simulated_cloud" / "inbox"
        rerender = set(deterministic_rerender_tasks([task["task_id"] for task in compiled["tasks"]], config["rerender_task_count"]))
        self.assertEqual(len(rerender), 2)
        for task in compiled["tasks"]:
            bundle = json.loads(Path(task["bundle_path"]).read_text(encoding="utf-8"))
            attempt = execute_fixture(bundle, ROOT / "runs" / "unit-phase4-merge" / "worker" / task["task_id"], attempt_id="A001")
            qc = local_qc(bundle, attempt)
            upload_attempt(attempt, qc, cloud)
        for attempt_dir in list_attempt_dirs(cloud):
            task_id = attempt_dir.parent.name
            verdict = make_verdict(attempt_dir, compiled["hidden_check_summary"], rerender_selected=task_id in rerender)
            self.assertEqual(verdict["verdict"], "ACCEPTED")
        index = build_accepted_index(list_attempt_dirs(cloud), compiled["tasks"])
        delivery = merge_fixture(index, ROOT / "runs" / "unit-phase4-merge" / "merge", segment_start=config["segment_start_frame"], segment_end=config["segment_end_frame_exclusive"])
        self.assertTrue(index["complete"])
        self.assertEqual(delivery["state"], "COMPLETE")
        self.assertTrue(Path(delivery["final_path"]).exists())


if __name__ == "__main__":
    unittest.main()

