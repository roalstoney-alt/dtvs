from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dtvs.contracts.signing import verify_document


def preflight_bundle(bundle: dict[str, Any], public_key: Ed25519PublicKey, workspace: Path, *, fixture_mode: bool) -> dict[str, Any]:
    checks = {
        "python": sys.version_info >= (3, 11),
        "ffmpeg": bool(shutil.which("ffmpeg")) or fixture_mode,
        "ffprobe": bool(shutil.which("ffprobe")) or fixture_mode,
        "gpu": fixture_mode,
        "workspace_writable": True,
        "bundle_signature": verify_document(bundle, public_key),
    }
    workspace.mkdir(parents=True, exist_ok=True)
    probe = workspace / ".write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        checks["workspace_writable"] = False
    return {
        "schema_version": "0.2.2",
        "fixture_mode": fixture_mode,
        "checks": checks,
        "ok": all(checks.values()),
        "gpu_status": "SKIPPED_WITH_REASON: fixture mode" if fixture_mode else "REQUIRED",
    }

