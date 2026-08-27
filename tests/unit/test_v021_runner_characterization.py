import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts import dtvs_pilot

ROOT = Path(__file__).resolve().parents[2]


class V021RunnerCharacterizationTests(unittest.TestCase):
    def test_v021_config_loader_rejects_non_v021(self):
        cfg = ROOT / "runs" / "unit-v022-config.json"
        cfg.write_text(
            json.dumps(
                {
                    "spec_version": "0.2.2",
                    "pilot_id": "DTVS-P001",
                    "source_path": "inputs/source_master.mkv",
                    "subtitle_path": "inputs/subtitles_zh.srt",
                    "segment_start": "00:10:00.000",
                    "segment_duration_seconds": 1200,
                    "chunk_seconds": 60,
                    "target_width": 3840,
                    "target_height": 2160,
                    "realesrgan_executable": "tools/realesrgan.exe",
                    "realesrgan_model": "realesrgan-x4plus",
                }
            ),
            encoding="utf-8",
        )
        try:
            with self.assertRaisesRegex(ValueError, "only accepts v0.2.1"):
                dtvs_pilot.load_config(cfg)
        finally:
            cfg.unlink(missing_ok=True)

    def test_v021_runner_cli_can_be_called(self):
        cp = subprocess.run(
            [sys.executable, "scripts/dtvs_pilot.py", "preflight", "--config", "configs/metropolis_20m.json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        data = json.loads(cp.stdout)
        self.assertEqual(data["runner"], "v0.2.1")
        self.assertEqual(data["spec_version"], "0.2.1")


if __name__ == "__main__":
    unittest.main()
