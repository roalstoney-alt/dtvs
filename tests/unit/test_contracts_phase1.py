from __future__ import annotations

import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dtvs.common import canonical_json
from dtvs.common.errors import FAILURE_CODES
from dtvs.contracts.models import FrameRange, TaskBundle
from dtvs.contracts.signing import generate_private_key, public_key_bytes, sign_document, verify_document
from dtvs.contracts.state_machine import transition
from dtvs.contracts.validation import validate_document

ROOT = Path(__file__).resolve().parents[2]


def sample_bundle() -> dict:
    bundle = TaskBundle(
        task_id="DTVS-P001-T0001",
        bundle_version=1,
        asset_id="sha256:" + "a" * 64,
        core=FrameRange(0, 1440),
        context=FrameRange(0, 1456),
        input={"path_or_object_key": "objects/source.mkv", "sha256": "b" * 64},
        execution={
            "worker_pack_version": "0.1.0",
            "pipeline_id": "restoration_realesrgan_v1",
            "model_sha256": "c" * 64,
            "parameters_sha256": "d" * 64,
            "random_seed": 20260827,
        },
        output={"width": 3840, "height": 2160, "fps_num": 24, "fps_den": 1, "expected_core_frames": 1440},
        lease={"expires_at": "2026-08-27T06:00:00+00:00", "checkpoint_frames": 120},
        verification={"upload_threshold": 90, "minimum_component_score": 70},
    )
    return bundle.to_dict()


class Phase1ContractTests(unittest.TestCase):
    def test_canonical_json_is_stable(self):
        self.assertEqual(canonical_json.dumps({"b": 1, "a": 2}), canonical_json.dumps({"a": 2, "b": 1}))

    def test_ed25519_signature_rejects_tampering(self):
        key = generate_private_key()
        signed = sign_document(sample_bundle(), key, "pilot-local-001")
        pub = Ed25519PublicKey.from_public_bytes(public_key_bytes(key))
        self.assertTrue(verify_document(signed, pub))
        signed["output"]["expected_core_frames"] = 1439
        self.assertFalse(verify_document(signed, pub))

    def test_task_bundle_schema_accepts_signed_bundle(self):
        key = generate_private_key()
        signed = sign_document(sample_bundle(), key, "pilot-local-001")
        validate_document(signed, ROOT / "schemas/task_bundle_v022.schema.json")

    def test_worker_cannot_write_accepted(self):
        with self.assertRaises(PermissionError):
            transition("CLOUD_CHECKING", "ACCEPTED", actor="worker", reason_code="OK", evidence={"x": 1})

    def test_illegal_transition_rejected(self):
        with self.assertRaises(ValueError):
            transition("CREATED", "ACCEPTED", actor="verifier", reason_code="OK", evidence={"x": 1})

    def test_failure_codes_cover_spec_minimums(self):
        for code in [
            "BUNDLE_SIGNATURE_INVALID",
            "INPUT_HASH_MISMATCH",
            "ENVIRONMENT_UNSUPPORTED",
            "OUTPUT_STRUCTURE_INVALID",
            "LOCAL_SCORE_BELOW_THRESHOLD",
            "EVIDENCE_INCOMPLETE",
            "CLOUD_HIDDEN_CHECK_FAILED",
            "LEASE_EXPIRED",
            "DUPLICATE_ACCEPTED_RESULT",
        ]:
            self.assertIn(code, FAILURE_CODES)


if __name__ == "__main__":
    unittest.main()
