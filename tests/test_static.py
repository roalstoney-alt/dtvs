import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StaticContractTests(unittest.TestCase):
    def test_config_is_frozen_to_20_minutes(self):
        cfg = json.loads((ROOT / "configs/metropolis_20m.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["spec_version"], "0.2.1")
        self.assertEqual(cfg["segment_duration_seconds"], 1200)
        self.assertEqual(cfg["chunk_seconds"], 60)
        self.assertEqual(cfg["segment_duration_seconds"] % cfg["chunk_seconds"], 0)
        self.assertEqual((cfg["target_width"], cfg["target_height"]), (3840, 2160))
        self.assertEqual(cfg["subtitle_timeline"], "full_source")

    def test_required_public_files_exist(self):
        for rel in [
            "README.md",
            "ORIGIN.md",
            "LICENSE",
            "CHANGELOG.md",
            "CITATION.cff",
            "spec/DTVS_SPEC_v0.2.1_SINGLE_NODE_PILOT.md",
            "spec/DTVS_SPEC_v0.2.2_ASYMMETRIC_VERIFIED_PIPELINE.md",
            "docs/CODEX_WORKER_PACK_V0.1_IMPLEMENTATION_WORKFLOW_CN.md",
            "pilot/METROPOLIS_20M_SINGLE_NODE.md",
            "scripts/dtvs_pilot.py",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_v022_frozen_contract_has_separate_gates(self):
        text = (ROOT / "spec/DTVS_SPEC_v0.2.2_ASYMMETRIC_VERIFIED_PIPELINE.md").read_text(encoding="utf-8")
        for required in ["FROZEN", "LAS >= 90", "NRS", "保密验证点", "ACCEPTED", "中位数"]:
            self.assertIn(required, text)
        self.assertIn("不是中心最终验收", text)

    def test_worker_pack_plan_preserves_role_boundary(self):
        text = (ROOT / "docs/CODEX_WORKER_PACK_V0.1_IMPLEMENTATION_WORKFLOW_CN.md").read_text(encoding="utf-8")
        for required in ["Coordinator", "Worker Pack", "Cloud Verifier", "Merger", "Worker 最高只能写到 `UPLOADED`", "Phase 0"]:
            self.assertIn(required, text)

    def test_media_is_gitignored(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("inputs/**", text)
        self.assertIn("*.mkv", text)
        self.assertIn(".dtvs_keys/**", text)


if __name__ == "__main__":
    unittest.main()

