from __future__ import annotations

import json
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dtvs.coordinator.asset_freezer import freeze_asset
from dtvs.coordinator.scene_splitter import assert_contiguous, split_fixed
from dtvs.coordinator.task_compiler import compile_tasks
from dtvs.contracts.signing import generate_private_key, public_key_bytes, verify_document

ROOT = Path(__file__).resolve().parents[2]


class Phase2CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "configs/metropolis_20m_v022.json").read_text(encoding="utf-8"))

    def test_fixture_freezer_records_rights_without_claiming_public_domain(self):
        asset = freeze_asset(self.config, ROOT)
        self.assertEqual(asset["schema_version"], "0.2.2")
        self.assertTrue(asset["rights_record"]["public_domain_claim_not_verified_by_software"])
        self.assertTrue(asset["fixture_mode"])

    def test_splitter_produces_20_contiguous_tasks(self):
        asset = freeze_asset(self.config, ROOT)
        ranges = split_fixed(asset, self.config)
        self.assertEqual(len(ranges), 20)
        assert_contiguous(ranges, 0, 28800)
        self.assertEqual(sum(r["end_frame_exclusive"] - r["start_frame"] for r in ranges), 28800)

    def test_compiler_signs_all_bundles_and_hides_secret_positions(self):
        asset = freeze_asset(self.config, ROOT)
        out = ROOT / "runs" / "unit-phase2" / "coordinator" / "bundles"
        key = generate_private_key()
        compiled = compile_tasks(
            asset,
            self.config,
            private_key=key,
            key_id="pilot-local-001",
            output_dir=out,
            hidden_secret=b"unit-secret",
        )
        pub = Ed25519PublicKey.from_public_bytes(public_key_bytes(key))
        self.assertEqual(len(compiled["tasks"]), 20)
        for task in compiled["tasks"]:
            doc = json.loads(Path(task["bundle_path"]).read_text(encoding="utf-8"))
            self.assertTrue(verify_document(doc, pub))
        hidden_text = json.dumps(compiled["hidden_check_summary"])
        self.assertIn("frame_commitment", hidden_text)
        self.assertNotIn('"frame"', hidden_text)


if __name__ == "__main__":
    unittest.main()

