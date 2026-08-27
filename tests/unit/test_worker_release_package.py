from __future__ import annotations

import base64
import json
import unittest
import zipfile
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dtvs.common.canonical_json import dumps
from dtvs.common.hashing import sha256_file

ROOT = Path(__file__).resolve().parents[2]


class WorkerReleasePackageTests(unittest.TestCase):
    def test_release_package_manifest_and_signature(self):
        zip_path = ROOT / "dist" / "DTVS-Worker-Pack-v0.1.0-Windows-x64.zip"
        manifest_path = ROOT / "dist" / "worker_release_manifest.json"
        sig_path = ROOT / "dist" / "worker_release_manifest.sig"
        self.assertTrue(zip_path.exists())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["zip"]["sha256"], sha256_file(zip_path))
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(manifest["release_manifest_public_key_b64"]))
        try:
            key.verify(base64.b64decode(sig_path.read_text(encoding="ascii").strip()), dumps(manifest))
        except InvalidSignature as exc:
            raise AssertionError("release manifest signature invalid") from exc
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        self.assertIn("DTVS-Worker-Pack-v0.1.0-Windows-x64/dtvs-worker.ps1", names)
        self.assertIn("DTVS-Worker-Pack-v0.1.0-Windows-x64/START_DTVS_WORKER.cmd", names)
        forbidden = [name for name in names if "/inputs/" in name or "/runs/" in name or "/reports/" in name or "/dist/" in name]
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()

