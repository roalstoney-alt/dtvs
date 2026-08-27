from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dtvs.contracts.signing import verify_document
from dtvs.contracts.validation import validate_document


def load_bundle(path: Path, public_key: Ed25519PublicKey) -> dict:
    bundle = json.loads(path.read_text(encoding="utf-8"))
    validate_document(bundle, Path("schemas/task_bundle_v022.schema.json"))
    if not verify_document(bundle, public_key):
        raise ValueError("BUNDLE_SIGNATURE_INVALID")
    return bundle

