from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from dtvs.common import canonical_json


def generate_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def save_private_key(path: Path, key: Ed25519PrivateKey) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def load_private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("expected Ed25519 private key")
    return key


def public_key_bytes(key: Ed25519PrivateKey | Ed25519PublicKey) -> bytes:
    pub = key.public_key() if isinstance(key, Ed25519PrivateKey) else key
    return pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def signature_payload(document: dict[str, Any]) -> bytes:
    payload = dict(document)
    payload.pop("signature", None)
    return canonical_json.dumps(payload)


def sign_document(document: dict[str, Any], key: Ed25519PrivateKey, key_id: str) -> dict[str, Any]:
    signed = dict(document)
    sig = key.sign(signature_payload(signed))
    signed["signature"] = {
        "key_id": key_id,
        "algorithm": "Ed25519",
        "value": base64.b64encode(sig).decode("ascii"),
    }
    return signed


def verify_document(document: dict[str, Any], public_key: Ed25519PublicKey) -> bool:
    signature = document.get("signature") or {}
    if signature.get("algorithm") != "Ed25519":
        return False
    try:
        public_key.verify(base64.b64decode(signature["value"]), signature_payload(document))
        return True
    except (InvalidSignature, KeyError, ValueError):
        return False

