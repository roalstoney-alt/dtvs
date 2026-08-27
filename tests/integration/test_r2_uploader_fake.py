from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

from dtvs.storage.r2_wrangler import upload_and_verify

ROOT = Path(__file__).resolve().parents[2]


class FakeRunner:
    def __init__(self, corrupt_download: bool = False):
        self.corrupt_download = corrupt_download

    def run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if cmd[:4] == ["npx", "wrangler", "r2", "object"] and cmd[4] == "put":
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:4] == ["npx", "wrangler", "r2", "object"] and cmd[4] == "get":
            target = Path(cmd[-1])
            if self.corrupt_download:
                target.write_text("bad", encoding="utf-8")
            else:
                source = ROOT / "runs" / "unit-r2-fake" / "task-inputs" / "T0001" / "input_with_context.mkv"
                shutil.copyfile(source, target)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "unexpected")


class R2UploaderFakeTests(unittest.TestCase):
    def setUp(self):
        self.run = ROOT / "runs" / "unit-r2-fake"
        file = self.run / "task-inputs" / "T0001" / "input_with_context.mkv"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("payload", encoding="utf-8")
        self.manifest = {
            "run_id": "unit-r2-fake",
            "bucket": "dtvs-pilot-assets",
            "objects": [
                {
                    "local_path": "task-inputs/T0001/input_with_context.mkv",
                    "object_key": "runs/unit-r2-fake/task-inputs/T0001/input_with_context.mkv",
                    "bytes": file.stat().st_size,
                    "sha256": "239f59ed55e737c77147cf55ad0c1b030b6d7ee748a7426952f9b852d5a935e5",
                    "content_type": "video/x-matroska",
                }
            ],
        }

    def test_receipt_verified_only_after_download_hash_match(self):
        receipt = upload_and_verify(self.manifest, self.run, runner=FakeRunner())
        self.assertEqual(receipt["state"], "VERIFIED")
        self.assertEqual(receipt["summary"]["verified"], 1)

    def test_download_hash_mismatch_is_partial(self):
        receipt = upload_and_verify(self.manifest, self.run, runner=FakeRunner(corrupt_download=True))
        self.assertEqual(receipt["state"], "PARTIAL")
        self.assertEqual(receipt["summary"]["failed"], 1)


if __name__ == "__main__":
    unittest.main()
