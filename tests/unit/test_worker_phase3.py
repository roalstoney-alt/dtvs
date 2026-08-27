from __future__ import annotations

import json
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dtvs.coordinator.asset_freezer import freeze_asset
from dtvs.coordinator.task_compiler import compile_tasks
from dtvs.contracts.signing import generate_private_key, public_key_bytes
from dtvs.worker.executor import execute_fixture
from dtvs.worker.local_qc import compute_las, local_qc
from dtvs.worker.preflight import preflight_bundle
from dtvs.worker.uploader import upload_attempt

ROOT = Path(__file__).resolve().parents[2]


class Phase3WorkerTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "configs/metropolis_20m_v022.json").read_text(encoding="utf-8"))
        self.key = generate_private_key()
        self.pub = Ed25519PublicKey.from_public_bytes(public_key_bytes(self.key))
        asset = freeze_asset(self.config, ROOT)
        out = ROOT / "runs" / "unit-phase3" / "bundles"
        compiled = compile_tasks(asset, self.config, private_key=self.key, key_id="pilot-local-001", output_dir=out, hidden_secret=b"s")
        self.bundle = json.loads(Path(compiled["tasks"][0]["bundle_path"]).read_text(encoding="utf-8"))

    def test_preflight_and_upload_pass_for_fixture_output(self):
        attempt_dir = ROOT / "runs" / "unit-phase3" / "worker" / "attempt-1"
        pf = preflight_bundle(self.bundle, self.pub, attempt_dir, fixture_mode=True)
        self.assertTrue(pf["ok"])
        attempt = execute_fixture(self.bundle, attempt_dir, attempt_id="A001")
        qc = local_qc(self.bundle, attempt)
        self.assertTrue(qc["upload_allowed"])
        result = upload_attempt(attempt, qc, ROOT / "runs" / "unit-phase3" / "simulated_cloud" / "inbox")
        self.assertTrue(result["video_uploaded"])
        self.assertTrue((Path(result["uploaded_to"]) / "core_output.fixture").exists())

    def test_failed_hard_gate_does_not_upload_video(self):
        attempt_dir = ROOT / "runs" / "unit-phase3" / "worker" / "attempt-2"
        attempt = execute_fixture(self.bundle, attempt_dir, attempt_id="A002", frame_count_delta=-1)
        qc = local_qc(self.bundle, attempt)
        self.assertFalse(qc["upload_allowed"])
        result = upload_attempt(attempt, qc, ROOT / "runs" / "unit-phase3" / "simulated_cloud" / "inbox")
        uploaded = Path(result["uploaded_to"])
        self.assertFalse((uploaded / "core_output.fixture").exists())
        self.assertTrue((uploaded / "failure_report.json").exists())

    def test_las_threshold_and_component_threshold(self):
        self.assertEqual(compute_las({name: 100 for name in ["structure_anchor", "temporal_consistency", "artifact_hallucination", "luma_color", "boundary_continuity"]})["score"], 100)
        attempt = execute_fixture(self.bundle, ROOT / "runs" / "unit-phase3" / "worker" / "attempt-3", attempt_id="A003")
        qc = local_qc(self.bundle, attempt, force_low_score=True)
        self.assertFalse(qc["upload_allowed"])
        self.assertEqual(qc["test_injection"], "TEST_INJECTION")


if __name__ == "__main__":
    unittest.main()

