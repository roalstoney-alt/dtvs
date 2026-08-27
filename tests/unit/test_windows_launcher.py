from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "dist" / "windows-launcher"


class WindowsLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ps1_bytes = (LAUNCHER / "run_dtvs_offline_pilot.ps1").read_bytes()
        cls.ps1 = cls.ps1_bytes.decode("utf-8-sig")

    def test_launcher_files_and_encoding(self):
        for name in [
            "START_DTVS_PILOT.cmd", "run_dtvs_offline_pilot.ps1", "README_CN.txt",
            "SHA256SUMS.txt", "run_dtvs_offline_pilot.ps1.before-encoding-fix",
            "START_DTVS_PILOT.cmd.before-encoding-fix",
        ]:
            self.assertTrue((LAUNCHER / name).exists(), name)
        self.assertTrue(self.ps1_bytes.startswith(b"\xef\xbb\xbf"))
        self.ps1.encode("ascii")
        cmd = (LAUNCHER / "START_DTVS_PILOT.cmd").read_text(encoding="utf-8")
        self.assertTrue(cmd.startswith("@echo off\nchcp 65001 >nul\nsetlocal\n"))

    def test_strict_file_discovery_and_three_way_hash(self):
        self.assertIn('Find-OneStrict "DTVS-Worker-Pack-*-Windows-x64.zip" "WORKER_ZIP"', self.ps1)
        self.assertIn('Find-OneStrict "DTVS-*-OFFLINE-HANDOFF.zip" "HANDOFF_ZIP"', self.ps1)
        for marker in ["*.partial", "*.zip.zip", "*.crdownload", "HASH_VERIFICATION_FAILED"]:
            self.assertIn(marker, self.ps1)
        self.assertIn("$entered -ne $published", self.ps1)
        self.assertIn("$entered -ne $computed", self.ps1)
        self.assertIn("WORKER_PACKAGE_HASH_VERIFIED", self.ps1)
        self.assertIn("HANDOFF_PACKAGE_HASH_VERIFIED", self.ps1)

    def test_exit_codes_and_failure_codes_are_stable(self):
        for code in ["10", "20", "21", "22", "23", "30", "31", "40", "41", "50", "60"]:
            self.assertIn(code, self.ps1)
        for marker in [
            "HANDOFF_POST_EXTRACT_VERIFICATION_FAILED", "ENVIRONMENT_INSTALL_RESTART_REQUIRED",
            "WORKER_EXECUTION_FAILED_RECOVERABLE", "EXPORT_FAILED", "RETURN_ZIP_NOT_FOUND",
        ]:
            self.assertIn(marker, self.ps1)

    def test_safe_extract_reuse_and_no_force_overwrite(self):
        for marker in ["Test-ZipSafe", "IsPathRooted", "ZIP_PATH_TRAVERSAL", "ZIP_REPARSE_POINT", "EXTRACT_REUSED"]:
            self.assertIn(marker, self.ps1)
        self.assertNotIn("Expand-Archive -Force", self.ps1)
        self.assertIn(".dtvs_extract_verified.json", self.ps1)

    def test_handoff_verification_and_forbidden_content(self):
        for marker in [
            "offline_assignment.json", "task_bundle.json", "input_with_context.mkv",
            "handoff_manifest.json", "SHA256SUMS.txt", "ACCEPTED_STATE_FORBIDDEN",
            "source_master.webm", "source_20m_video_cfr.mkv", "hidden_checks.json",
            "private_key", ".dev.vars", "import_handoff_tasks",
        ]:
            self.assertIn(marker, self.ps1)

    def test_doctor_policy_and_real_report_fields(self):
        for marker in [
            "dtvs-worker.ps1", "doctor", "doctor-latest.json", "Gyan.FFmpeg", "winget install --id Gyan.FFmpeg --source winget",
            "NVIDIA driver", "Real-ESRGAN", "model_sha256", "driver_version", "ffmpeg_version",
            "realesrgan_version", "worker_pack_version",
        ]:
            self.assertIn(marker, self.ps1)
        self.assertNotIn("--skip-doctor", self.ps1)
        self.assertNotIn("See doctor log", self.ps1)
        self.assertIn("Doctor field unavailable:", self.ps1)

    def test_run_export_paths_and_no_task_logic(self):
        self.assertIn("--package $handoffPackageRoot --workspace $Workspace", self.ps1)
        self.assertIn("export --workspace $Workspace --run-id $RunId --destination $Output", self.ps1)
        for marker in ["pilot_terminal_report.json", "pilot_terminal_report.md", "task-summary.csv"]:
            self.assertIn(marker, self.ps1)
        self.assertNotIn("K:\\dtvs", self.ps1)
        self.assertNotRegex(self.ps1, r"\bLAS\b")
        self.assertNotIn("returnManifestHash", self.ps1)
        self.assertNotIn("Set-Content.*return_manifest.sig", self.ps1)

    def test_return_selection_and_real_signature_only(self):
        self.assertIn("return_zip_path", self.ps1)
        self.assertIn("RETURN_ZIP_CONFLICT", self.ps1)
        self.assertIn("RETURN_MANIFEST_SIGNATURE_MISSING", self.ps1)
        self.assertIn("RETURN_MANIFEST_SIGNATURE_IS_HASH", self.ps1)
        self.assertIn("verify-return", self.ps1)
        self.assertNotIn("Sort-Object LastWriteTime", self.ps1)
        self.assertNotIn("Select-Object -First 1", self.ps1)
        self.assertNotIn("Get-FileHash.*return_manifest.sig", self.ps1)
        self.assertIn("if ($null -eq $ReturnZip)", self.ps1)

    def test_self_test_verify_only_and_no_render(self):
        for marker in [
            "[switch]$SelfTest", "[switch]$VerifyOnly", "LAUNCHER_SELF_TEST_PASS",
            "LAUNCHER_VERIFY_ONLY_PASS", "Assert-ScriptParsePass", "POWERSHELL_51_PARSE_PASS",
        ]:
            self.assertIn(marker, self.ps1)
        self.assertIn("if ($SelfTest)", self.ps1)
        self.assertIn("if ($VerifyOnly)", self.ps1)
        self.assertNotIn(" run --package ", self.ps1.split("function Invoke-SelfTest", 1)[1].split("function Invoke-VerifyOnly", 1)[0])

    def test_markdown_here_string_and_ps51_static_compatibility(self):
        self.assertIn('$markdown = @"', self.ps1)
        self.assertIn('"@\n  Write-Utf8Text', self.ps1)
        for token in ["&&", "||", "ForEach-Object -Parallel", "??", "?."]:
            self.assertNotIn(token, self.ps1)
        self.assertIn("Add-Type -AssemblyName System.IO.Compression.FileSystem", self.ps1)

    def test_sha256sums_matches_launcher_files(self):
        entries = {}
        for line in (LAUNCHER / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            digest, path = line.split(maxsplit=1)
            entries[Path(path).name] = digest
        for name in ["START_DTVS_PILOT.cmd", "run_dtvs_offline_pilot.ps1", "README_CN.txt"]:
            self.assertEqual(entries[name], hashlib.sha256((LAUNCHER / name).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
