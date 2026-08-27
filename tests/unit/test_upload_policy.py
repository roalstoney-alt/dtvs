from __future__ import annotations

import unittest
from pathlib import Path

from dtvs.storage.upload_policy import classify_allowed, validate_run_id

ROOT = Path(__file__).resolve().parents[2]


class UploadPolicyTests(unittest.TestCase):
    def test_run_id_safe_chars(self):
        validate_run_id("DTVS-P001-20260827T000000Z")
        with self.assertRaises(ValueError):
            validate_run_id("../bad")

    def test_forbidden_names_rejected(self):
        path = ROOT / "runs" / "unit-policy" / "source_20m_video_cfr.mkv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError):
            classify_allowed(path, 330301440)

    def test_315mib_limit_rejected(self):
        path = ROOT / "runs" / "unit-policy" / "task-inputs" / "T0001" / "input_with_context.mkv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError):
            classify_allowed(path, 0)


if __name__ == "__main__":
    unittest.main()

