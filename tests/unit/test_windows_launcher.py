from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "dist" / "windows-launcher"


class WindowsLauncherTests(unittest.TestCase):
    def test_launcher_files_exist_and_cmd_is_only_wrapper(self):
        cmd = LAUNCHER / "START_DTVS_PILOT.cmd"
        ps1 = LAUNCHER / "run_dtvs_offline_pilot.ps1"
        readme = LAUNCHER / "README_CN.txt"
        sums = LAUNCHER / "SHA256SUMS.txt"
        for path in [cmd, ps1, readme, sums]:
            self.assertTrue(path.exists(), path)
        self.assertEqual(
            cmd.read_text(encoding="utf-8").replace("\r\n", "\n"),
            """@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_dtvs_offline_pilot.ps1"
set "DTVS_EXIT=%ERRORLEVEL%"
echo.
if not "%DTVS_EXIT%"=="0" (
  echo DTVS Pilot stopped with exit code %DTVS_EXIT%.
) else (
  echo DTVS Pilot completed.
)
pause
exit /b %DTVS_EXIT%
""",
        )

    def test_strict_file_discovery_and_hash_prompts(self):
        text = (LAUNCHER / "run_dtvs_offline_pilot.ps1").read_text(encoding="utf-8")
        self.assertIn('Find-OneStrict "DTVS-Worker-Pack-*-Windows-x64.zip" "WORKER_ZIP"', text)
        self.assertIn('Find-OneStrict "DTVS-*-OFFLINE-HANDOFF.zip" "HANDOFF_ZIP"', text)
        self.assertIn("*.partial", text)
        self.assertIn("*.zip.zip", text)
        self.assertIn("请输入Worker Pack SHA-256", text)
        self.assertIn("请输入Handoff SHA-256", text)
        self.assertIn("HASH_VERIFICATION_FAILED", text)
        self.assertIn("WORKER_PACKAGE_HASH_VERIFIED", text)
        self.assertIn("HANDOFF_PACKAGE_HASH_VERIFIED", text)
        self.assertRegex(text, r"entered.*published|published.*computed|entered.*computed")

    def test_exit_codes_and_failure_codes_are_stable(self):
        text = (LAUNCHER / "run_dtvs_offline_pilot.ps1").read_text(encoding="utf-8")
        for code in ["10", "20", "21", "22", "23", "30", "31", "40", "41", "50", "60"]:
            self.assertRegex(text, rf"\b{code}\b")
        for marker in [
            "HANDOFF_POST_EXTRACT_VERIFICATION_FAILED",
            "ENVIRONMENT_INSTALL_RESTART_REQUIRED",
            "WORKER_EXECUTION_FAILED_RECOVERABLE",
            "EXPORT_FAILED",
        ]:
            self.assertIn(marker, text)

    def test_safe_extract_reuse_and_no_force_overwrite(self):
        text = (LAUNCHER / "run_dtvs_offline_pilot.ps1").read_text(encoding="utf-8")
        self.assertIn("Test-ZipSafe", text)
        self.assertIn("IsPathRooted", text)
        self.assertIn("ZIP_PATH_TRAVERSAL", text)
        self.assertIn("ZIP_REPARSE_POINT", text)
        self.assertIn("EXTRACT_REUSED", text)
        self.assertNotIn("Expand-Archive -Force", text)

    def test_handoff_verification_and_forbidden_content(self):
        text = (LAUNCHER / "run_dtvs_offline_pilot.ps1").read_text(encoding="utf-8")
        for marker in [
            "offline_assignment.json",
            "task_bundle.json",
            "input_with_context.mkv",
            "handoff_manifest.json",
            "SHA256SUMS.txt",
            "ACCEPTED_STATE_FORBIDDEN",
            "source_master.webm",
            "source_20m_video_cfr.mkv",
            "hidden_checks.json",
            "private_key",
            ".dev.vars",
        ]:
            self.assertIn(marker, text)

    def test_doctor_install_policy_and_no_skip_doctor(self):
        text = (LAUNCHER / "run_dtvs_offline_pilot.ps1").read_text(encoding="utf-8")
        self.assertIn("dtvs-worker.ps1", text)
        self.assertIn("doctor", text)
        self.assertIn("doctor-latest.json", text)
        self.assertIn("Gyan.FFmpeg", text)
        self.assertIn("winget install --id Gyan.FFmpeg --source winget", text)
        self.assertIn("NVIDIA驱动", text)
        self.assertIn("Real-ESRGAN", text)
        self.assertNotIn("--skip-doctor", text)

    def test_confirm_run_export_output_and_paths_with_spaces(self):
        text = (LAUNCHER / "run_dtvs_offline_pilot.ps1").read_text(encoding="utf-8")
        self.assertIn("是否开始执行？[Y/N]", text)
        self.assertIn("--package $handoffPackageRoot --workspace $Workspace", text)
        self.assertIn("export --workspace $Workspace --run-id $RunId --destination $Output", text)
        self.assertIn("DTVS-P001-RETURN.zip", text)
        self.assertIn("pilot_terminal_report.json", text)
        self.assertIn("task-summary.csv", text)
        self.assertNotIn("K:\\dtvs", text)

    def test_powershell_51_compatibility_static(self):
        text = (LAUNCHER / "run_dtvs_offline_pilot.ps1").read_text(encoding="utf-8")
        forbidden_ps7 = ["&&", "||", "ForEach-Object -Parallel", "??", "?."]
        for token in forbidden_ps7:
            self.assertNotIn(token, text)
        self.assertIn("Add-Type -AssemblyName System.IO.Compression.FileSystem", text)

    def test_sha256sums_matches_launcher_files(self):
        entries = {}
        for line in (LAUNCHER / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            digest, path = line.split(maxsplit=1)
            entries[Path(path).name] = digest
        for name in ["START_DTVS_PILOT.cmd", "run_dtvs_offline_pilot.ps1", "README_CN.txt"]:
            digest = hashlib.sha256((LAUNCHER / name).read_bytes()).hexdigest()
            self.assertEqual(entries[name], digest)


if __name__ == "__main__":
    unittest.main()

