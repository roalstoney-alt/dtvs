from __future__ import annotations

import copy
import hashlib
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator, ValidationError

from dtvs.common.canonical_json import dumps
from dtvs.contracts.signing import generate_private_key, sign_document
from dtvs.scheduling.network_profile import validate_schema
from dtvs.scheduling.placement_policy import COMMON_PERMISSIONS, digest
from dtvs.scheduling.replay import replay, run_files

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/p0c_placement"
AS_OF = "2026-11-04T12:10:00Z"


def rechain(dataset: dict) -> None:
    previous = "0" * 64
    for event in dataset["events"]:
        event["prev_sha256"] = previous
        event.pop("sha256", None)
        event["sha256"] = digest(event)
        previous = event["sha256"]


class P0CPlacementTests(unittest.TestCase):
    def setUp(self):
        self.dataset = json.loads((FIXTURE / "dataset.json").read_text())
        self.fixture = (FIXTURE / "fixture.txt").read_bytes()
        self.key = generate_private_key()
        self.resign()

    def resign(self):
        for task in self.dataset["tasks"]:
            task["bundle"] = sign_document(task["bundle"], self.key, "unit-test-only")
            task["authorization"]["bundle_sha256"] = digest(task["bundle"])
            task["authorization"] = sign_document(task["authorization"], self.key, "unit-test-only")

    def run_replay(self):
        return replay(self.dataset, self.fixture, self.key.public_key(), as_of=AS_OF)

    def first_task_decisions(self):
        return [d for d in self.run_replay()["decisions"] if d["task_id"] == "DTVS-P001-T0001"]

    def assert_first_held(self, status):
        decisions = self.first_task_decisions()
        self.assertEqual(len(decisions), 3)
        for decision in decisions:
            self.assertEqual(decision["status"], status)
            self.assertIsNone(decision["selected_route"])
            self.assertIsNone(decision["relative_regret"])

    def test_end_to_end_observed_profiles_only_and_baselines(self):
        result = self.run_replay()
        self.assertEqual((result["observations"], result["holdout_decisions"]), (24, 6))
        self.assertEqual(result["selected_decisions"], 6)
        self.assertAlmostEqual(result["max_relative_regret"], 2 / 9)
        for value in result["audit"].values():
            self.assertEqual(value, 0)
        for decision in result["decisions"]:
            self.assertEqual(decision["feasible_set"], ["A_LOCAL", "B_DIRECT", "C_RANGE"])
            self.assertNotIn("D_REMOTE", decision["heldout_seconds"])
            self.assertEqual(set(decision["baselines"]), {"always_local", "always_direct", "always_range"})
            self.assertTrue(all(b["status"] == "EVALUATED" for b in decision["baselines"].values()))

    def test_missing_profile_holds_even_with_local_available(self):
        self.dataset["profiles"] = self.dataset["profiles"][1:]
        self.assert_first_held("HOLD_NOT_CALIBRATED")

    def test_stale_profile_holds(self):
        self.dataset["profiles"][0]["ttl_seconds"] = 599
        self.assert_first_held("HOLD_NOT_CALIBRATED")

    def test_ttl_boundary_uses_observation_end(self):
        profile = self.dataset["profiles"][0]
        profile["ttl_seconds"] = 600
        self.assertEqual(self.first_task_decisions()[0]["status"], "SELECTED_OFFLINE")
        profile["recorded_at"] = AS_OF
        profile["ttl_seconds"] = 599
        self.assert_first_held("HOLD_NOT_CALIBRATED")

    def test_reverse_profile_never_substitutes_forward_direction(self):
        profile = self.dataset["profiles"][0]
        profile["source_id"], profile["destination_id"] = profile["destination_id"], profile["source_id"]
        self.assert_first_held("HOLD_NOT_CALIBRATED")
        self.assertIn("DIRECTION_MISMATCH", self.first_task_decisions()[0]["reason_codes"])

    def test_unknown_topology_holds(self):
        self.dataset["profiles"][0]["route_context"]["topology_id"] = None
        self.assert_first_held("HOLD_NOT_CALIBRATED")

    def test_profile_time_direction_source_and_anomaly_adverse_cases(self):
        original = copy.deepcopy(self.dataset["profiles"][0])
        for field, value in [
            ("recorded_at", "2026-11-04T12:11:00Z"),
            ("recorded_at", "2026-11-04T12:00:00"),
            ("recorded_at", "2026-11-04T14:00:00+02:00"),
            ("source_sha256", "0" * 64),
            ("observed_mbps", None),
            ("conservative_mbps", 1000),
            ("anomaly_flags", ["REVERSE_DIRECTION_PAUSES_UNRESOLVED"]),
        ]:
            with self.subTest(field=field, value=value):
                self.dataset["profiles"][0] = {**original, field: value}
                self.assert_first_held("HOLD_NOT_CALIBRATED")

    def test_missing_return_direction_holds(self):
        self.dataset["tasks"][0]["authorization"]["candidates"][1]["network_hops"].pop()
        self.resign()
        self.assert_first_held("HOLD_NOT_CALIBRATED")

    def test_missing_or_tampered_profile_source_holds(self):
        source = self.dataset["profile_sources"].pop("synthetic-old-out")
        self.assert_first_held("HOLD_NOT_CALIBRATED")
        source["observed_mbps"] = 999
        self.dataset["profile_sources"]["synthetic-old-out"] = source
        self.assert_first_held("HOLD_NOT_CALIBRATED")

    def test_profile_nonfinite_values_hold(self):
        for name in ("observed_mbps", "conservative_mbps", "variability_mbps"):
            with self.subTest(name=name):
                self.dataset["profiles"][0][name] = float("nan")
                self.assert_first_held("HOLD_NOT_CALIBRATED")

    def test_every_unknown_permission_holds_not_speed_fallback(self):
        candidate = self.dataset["tasks"][0]["authorization"]["candidates"][1]
        for permission in (*COMMON_PERMISSIONS, "remote_execution_allowed"):
            with self.subTest(permission=permission):
                candidate["permissions"][permission] = None
                self.resign()
                self.assert_first_held("HOLD_ELIGIBILITY_UNKNOWN")
                candidate["permissions"][permission] = True

    def test_unknown_source_execution_permission_holds(self):
        self.dataset["tasks"][0]["authorization"]["candidates"][0]["permissions"].pop("source_execution_allowed")
        self.resign()
        self.assert_first_held("HOLD_ELIGIBILITY_UNKNOWN")

    def test_denied_fastest_route_is_not_selected_or_oracle(self):
        for decision in self.first_task_decisions():
            self.assertEqual(decision["candidate_gates"]["D_REMOTE"]["status"], "INELIGIBLE")
            self.assertGreaterEqual(decision["oracle_seconds"], 9)
            self.assertNotIn("D_REMOTE", decision["predictions_seconds"])

    def test_range_unsupported_excluded_from_policy_baseline_and_oracle(self):
        candidate = self.dataset["tasks"][0]["authorization"]["candidates"][2]
        candidate["permissions"]["range_supported"] = False
        self.resign()
        for decision in self.first_task_decisions():
            self.assertNotIn("C_RANGE", decision["feasible_set"])
            self.assertNotIn("C_RANGE", decision["predictions_seconds"])
            self.assertIsNone(decision["baselines"]["always_range"]["actual_seconds"])
            self.assertEqual(decision["oracle_seconds"], min(decision["heldout_seconds"].values()))

    def test_unknown_or_invalid_range_fraction_holds(self):
        candidate = self.dataset["tasks"][0]["authorization"]["candidates"][2]
        for fraction in [None, 0, 1.1, True]:
            with self.subTest(fraction=fraction):
                candidate["access_fraction"] = fraction
                self.resign()
                self.assert_first_held("HOLD_ELIGIBILITY_UNKNOWN")

    def test_denied_range_rights_exclude_c_path(self):
        self.dataset["tasks"][0]["authorization"]["candidates"][2]["permissions"]["asset_authorized"] = False
        self.resign()
        for decision in self.first_task_decisions():
            self.assertNotIn("C_RANGE", decision["heldout_seconds"])
            self.assertNotEqual(decision["selected_route"], "C_RANGE")

    def test_all_routes_denied_holds(self):
        for candidate in self.dataset["tasks"][0]["authorization"]["candidates"]:
            candidate["permissions"]["privacy_allowed"] = False
        self.resign()
        self.assert_first_held("HOLD_NO_FEASIBLE_ROUTE")

    def test_fixture_content_hash_mismatch_holds(self):
        self.fixture += b"tampered"
        self.assert_first_held("HOLD_INTEGRITY")

    def test_signature_cannot_be_replaced_by_asserted_state(self):
        self.dataset["tasks"][0]["bundle"]["signature"]["value"] = "invalid"
        self.assert_first_held("HOLD_INTEGRITY")

    def test_authorization_cannot_be_tampered_or_rebound(self):
        self.dataset["tasks"][0]["authorization"]["candidates"][3]["permissions"]["legal_allowed"] = True
        self.assert_first_held("HOLD_INTEGRITY")
        self.resign()
        self.dataset["tasks"][0]["authorization"]["bundle_sha256"] = "0" * 64
        self.dataset["tasks"][0]["authorization"] = sign_document(self.dataset["tasks"][0]["authorization"], self.key, "unit-test-only")
        self.assert_first_held("HOLD_INTEGRITY")

    def test_untrusted_key_holds(self):
        self.key = generate_private_key()
        self.assert_first_held("HOLD_INTEGRITY")

    def test_quality_gate_not_bypassable(self):
        authorization = self.dataset["tasks"][0]["authorization"]
        for name in ("verifier_required", "accepted_only_merge", "quality_gate_required"):
            with self.subTest(name=name):
                authorization[name] = False
                self.resign()
                self.assert_first_held("HOLD_QUALITY_GATE")
                authorization[name] = True
        self.dataset["tasks"][0]["bundle"]["verification"]["upload_threshold"] = 89
        self.resign()
        self.assert_first_held("HOLD_QUALITY_GATE")

    def test_missing_verifier_requirement_holds(self):
        del self.dataset["tasks"][0]["authorization"]["verifier_required"]
        self.resign()
        self.assert_first_held("HOLD_ELIGIBILITY_UNKNOWN")

    def test_nonfinite_or_invalid_quality_threshold_cannot_bypass_gate(self):
        for value in (float("nan"), float("inf"), True, "90", 101):
            with self.subTest(value=value):
                self.dataset["tasks"][0]["bundle"]["verification"]["upload_threshold"] = value
                self.resign()
                self.assert_first_held("HOLD_QUALITY_GATE")

    def test_terminal_bundle_and_expired_lease_hold(self):
        task = self.dataset["tasks"][0]
        task["authorization"]["bundle_state"] = "ACCEPTED"
        self.resign()
        self.assert_first_held("HOLD_QUALITY_GATE")
        task["authorization"]["bundle_state"] = "CREATED"
        task["bundle"]["lease"]["expires_at"] = AS_OF
        self.resign()
        self.assert_first_held("HOLD_QUALITY_GATE")

    def test_duplicate_event_or_duplicate_sample_rejected(self):
        self.dataset["events"].append(copy.deepcopy(self.dataset["events"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            self.run_replay()
        self.dataset["events"][-1]["event_id"] = "different-id-same-sample"
        rechain(self.dataset)
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            self.run_replay()

    def test_event_tampering_or_reordering_rejected(self):
        self.dataset["events"][0]["elapsed_seconds"] += 1
        with self.assertRaisesRegex(ValueError, "EVENT_CHAIN_TAMPERED"):
            self.run_replay()
        rechain(self.dataset)
        self.dataset["events"].reverse()
        with self.assertRaisesRegex(ValueError, "EVENT_CHAIN_TAMPERED"):
            self.run_replay()

    def test_nonfinite_latency_rejected(self):
        for value in (float("nan"), float("inf"), 0, -1, True):
            with self.subTest(value=value):
                self.dataset["events"][0]["elapsed_seconds"] = value
                rechain(self.dataset)
                with self.assertRaisesRegex(ValueError, "EVENT_LATENCY_INVALID"):
                    self.run_replay()

    def test_holdout_execution_times_do_not_affect_predictions_or_selection(self):
        before = self.first_task_decisions()[0]
        for event in self.dataset["events"]:
            if event["repeat_id"] == "repeat-1":
                event["elapsed_seconds"] *= 1000 if event["route_id"] == "B_DIRECT" else .001
        rechain(self.dataset)
        after = self.first_task_decisions()[0]
        self.assertEqual(before["predictions_seconds"], after["predictions_seconds"])
        self.assertEqual(before["selected_route"], after["selected_route"])
        self.assertNotEqual(before["relative_regret"], after["relative_regret"])
        events_by_hash = {event["sha256"]: event for event in self.dataset["events"]}
        for decision in self.run_replay()["decisions"]:
            for event_hash in decision["training_events"]:
                event = events_by_hash[event_hash]
                self.assertNotEqual(event["repeat_id"], decision["repeat_id"])
                self.assertEqual(event["environment_profile_id"], decision["environment_profile_id"])

    def test_environment_profiles_are_not_pooled(self):
        before = self.first_task_decisions()
        for event in self.dataset["events"]:
            if event["environment_profile_id"] == "synthetic-new":
                event["elapsed_seconds"] *= 12345
        rechain(self.dataset)
        after = self.first_task_decisions()
        self.assertEqual([d["predictions_seconds"] for d in before], [d["predictions_seconds"] for d in after])

    def test_missing_empirical_route_does_not_force_fallback(self):
        self.dataset["events"] = [e for e in self.dataset["events"] if e["route_id"] != "C_RANGE"]
        rechain(self.dataset)
        self.assert_first_held("HOLD_NOT_CALIBRATED")

    def test_one_repeat_does_not_train_on_itself(self):
        self.dataset["events"] = [e for e in self.dataset["events"] if e["repeat_id"] == "repeat-1"]
        rechain(self.dataset)
        result = self.run_replay()
        self.assertEqual(result["selected_decisions"], 0)
        for decision in result["decisions"]:
            self.assertEqual(decision["status"], "HOLD_NOT_CALIBRATED")
            self.assertEqual(decision["predictions_seconds"], {})
            self.assertEqual(decision["training_events"], [])

    def test_same_input_determinism_and_no_mutation(self):
        before = dumps(self.dataset)
        first = dumps(self.run_replay())
        self.assertEqual(first, dumps(self.run_replay()))
        self.assertEqual(before, dumps(self.dataset))

    def test_offline_replay_makes_no_socket_or_dispatch_calls(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
            self.assertEqual(self.run_replay()["audit"]["PRODUCTION_DISPATCH_COUNT"], 0)
        import ast
        forbidden = {"requests", "httpx", "socket", "subprocess", "dtvs.worker", "dtvs.pilot", "dtvs.storage"}
        for path in (ROOT / "dtvs/scheduling").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imports = [node.module or ""]
                else:
                    continue
                self.assertFalse(any(name == bad or name.startswith(bad + ".") for name in imports for bad in forbidden))

    def test_schemas_require_null_unmeasured_and_reject_extra_fields(self):
        for name in ("network_profile_v01.schema.json", "placement_decision_v01.schema.json"):
            Draft202012Validator.check_schema(json.loads((ROOT / "schemas" / name).read_text()))
        decision = self.run_replay()["decisions"][0]
        for field in ("currency", "energy", "confidence"):
            self.assertEqual(decision[field], {"status": "NOT_MEASURED", "value": None})
        decision["currency"]["value"] = .01
        with self.assertRaises(ValidationError):
            validate_schema(decision, "placement_decision_v01.schema.json")
        profile = self.dataset["profiles"][0]
        profile["confidence"] = .99
        with self.assertRaises(ValidationError):
            validate_schema(profile, "network_profile_v01.schema.json")

    def test_file_replay_preserves_inputs_and_rejects_output_overwrite(self):
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex((FIXTURE / "public_key.hex").read_text().strip()))
        before = {p.name: p.read_bytes() for p in FIXTURE.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "output"
            run_files(FIXTURE, out, public_key, as_of=AS_OF)
            output_before = {p.name: p.read_bytes() for p in out.iterdir()}
            with self.assertRaises(FileExistsError):
                run_files(FIXTURE, out, public_key, as_of=AS_OF)
            with self.assertRaises(FileExistsError):
                run_files(FIXTURE, FIXTURE, public_key, as_of=AS_OF)
            self.assertEqual(output_before, {p.name: p.read_bytes() for p in out.iterdir()})
            other = Path(directory) / "second"
            run_files(FIXTURE, other, public_key, as_of=AS_OF)
            self.assertEqual(output_before, {p.name: p.read_bytes() for p in other.iterdir()})
            manifest = json.loads((out / "manifest.json").read_text())
            for name, expected in manifest["files_sha256"].items():
                self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), expected)
            self.assertEqual((out / "manifest.json").stat().st_mode & 0o222, 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in FIXTURE.iterdir() if p.is_file()})

    def test_input_manifest_rejects_hash_mismatch_and_path_traversal(self):
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex((FIXTURE / "public_key.hex").read_text().strip()))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            for name in ("dataset.json", "fixture.txt", "manifest.json"):
                (source / name).write_bytes((FIXTURE / name).read_bytes())
            (source / "fixture.txt").write_bytes(b"different content")
            out = Path(directory) / "output"
            with self.assertRaisesRegex(ValueError, "INPUT_HASH_MISMATCH"):
                run_files(source, out, public_key, as_of=AS_OF)
            self.assertFalse(out.exists())
            manifest = json.loads((source / "manifest.json").read_text())
            manifest["files_sha256"]["../outside"] = "0" * 64
            (source / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "FILE_SET_INVALID"):
                run_files(source, out, public_key, as_of=AS_OF)


if __name__ == "__main__":
    unittest.main()
