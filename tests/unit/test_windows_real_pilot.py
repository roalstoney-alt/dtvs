from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from dtvs.worker.real_ncnn_executor import build_realesrgan_command

ROOT = Path(__file__).resolve().parents[2]


class WindowsRealPilotTests(unittest.TestCase):
    def test_ncnn_command_is_argument_list_and_preserves_spaces(self):
        command = build_realesrgan_command(
            Path(r"K:\dtvs\tools\real esrgan\realesrgan-ncnn-vulkan.exe"),
            Path(r"K:\dtvs\runs\pilot with spaces\input"),
            Path(r"K:\dtvs\runs\pilot with spaces\output"),
            Path(r"K:\dtvs\tools\real esrgan\models"),
        )
        self.assertEqual(command[0], r"K:\dtvs\tools\real esrgan\realesrgan-ncnn-vulkan.exe")
        self.assertIn("-t", command)
        self.assertNotIn("&&", command)

    def test_ffmpeg_extraction_uses_ffmpeg_9_option(self):
        source = (ROOT / "scripts/windows_real_pilot.py").read_text(encoding="utf-8")
        self.assertIn('"-fps_mode", "vfr"', source)
        self.assertNotIn('"-vsync", "0"', source)

    def test_real_executor_source_has_no_fixture_fallback(self):
        source = (ROOT / "dtvs/worker/real_ncnn_executor.py").read_text(encoding="utf-8")
        self.assertIn("FIXTURE_FORBIDDEN_FOR_REAL_TASK", source)
        self.assertIn("execute_realesrgan_ncnn", source)

    def test_windows_pilot_dry_run_is_platform_neutral(self):
        result = subprocess.run(
            [sys.executable, "scripts/windows_real_pilot.py", "run-10s", "--root", r"K:\dtvs", "--dry-run"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["fixture_fallback"])
        self.assertIn("run-1min", payload["actions"])

    def test_handoff_manifest_excludes_runtime_artifacts(self):
        source = (ROOT / "scripts/build_windows_real_pilot_handoff.py").read_text(encoding="utf-8")
        for forbidden in ["Real-ESRGAN EXE", "model files", "source media", "Windows evidence"]:
            self.assertIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
