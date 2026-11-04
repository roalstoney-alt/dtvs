"""Deterministic, file-only evaluation. No executor, network client, or dispatch.

Input hashes and event chains detect inconsistencies, not externally anchored
authenticity. A public key must be supplied separately by the caller.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dtvs.common.canonical_json import dumps
from dtvs.scheduling import POLICY_VERSION
from dtvs.scheduling.network_profile import utc, validate_schema
from dtvs.scheduling.placement_policy import candidate_gate, digest, rank, task_gate


def verify_events(events: list[dict]) -> None:
    previous, identities, samples = "0" * 64, set(), set()
    for event in events:
        identity = event["event_id"]
        sample = tuple(event[name] for name in ("environment_profile_id", "task_id", "repeat_id", "route_id"))
        if identity in identities or sample in samples:
            raise ValueError("DUPLICATE_EVENT_OR_SAMPLE")
        identities.add(identity)
        samples.add(sample)
        elapsed = event["elapsed_seconds"]
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed <= 0:
            raise ValueError("EVENT_LATENCY_INVALID")
        if any(not isinstance(event[name], str) or not event[name] for name in (
            "event_id", "repeat_id", "route_id", "task_id", "environment_profile_id",
        )):
            raise ValueError("EVENT_ID_INVALID")
        payload = {key: value for key, value in event.items() if key != "sha256"}
        if event["prev_sha256"] != previous or digest(payload) != event["sha256"]:
            raise ValueError("EVENT_CHAIN_TAMPERED")
        previous = event["sha256"]


def predict(training: list[dict], feasible: list[str]) -> dict[str, float]:
    """Empirical end-to-end mean per task/route/environment, never bandwidth math."""
    predictions = {}
    for route in feasible:
        values = [event["elapsed_seconds"] for event in training if event["route_id"] == route]
        if values:
            predictions[route] = math.fsum(values) / len(values)
    return predictions


def replay(dataset: dict, fixture: bytes, trusted_key: Ed25519PublicKey, *, as_of: str) -> dict:
    """Pure evaluation with leave-one-repeat-out and no cross-profile pooling.

    A fold's complete repeat (all routes) is excluded before prediction. Any
    otherwise eligible unknown route stops selection instead of forcing local.
    """
    utc(as_of)
    if dataset["input_mode"] not in {"SYNTHETIC_FIXTURE", "SANITIZED_OBSERVATIONS"}:
        raise ValueError("INPUT_MODE_UNSUPPORTED")
    events = dataset["events"]
    verify_events(events)
    profiles = {profile["profile_id"]: profile for profile in dataset["profiles"]}
    if len(profiles) != len(dataset["profiles"]):
        raise ValueError("DUPLICATE_PROFILE")
    tasks = {(task["environment_profile_id"], task["task_id"]): task for task in dataset["tasks"]}
    if len(tasks) != len(dataset["tasks"]):
        raise ValueError("DUPLICATE_TASK")
    if not tasks or not events:
        raise ValueError("EMPTY_REPLAY")
    for event in events:
        task = tasks.get((event["environment_profile_id"], event["task_id"]))
        if task is None or event["route_id"] not in {c["route_id"] for c in task["authorization"]["candidates"]}:
            raise ValueError("EVENT_TASK_OR_ROUTE_UNKNOWN")
    if set(tasks) != {(event["environment_profile_id"], event["task_id"]) for event in events}:
        raise ValueError("TASK_WITHOUT_OBSERVATIONS")
    fixture_hash, decisions = hashlib.sha256(fixture).hexdigest(), []
    for (environment, task_id), task in sorted(tasks.items()):
        reasons = task_gate(task, fixture, trusted_key, as_of)
        candidates = task["authorization"]["candidates"]
        gates = {} if reasons else {
            c["route_id"]: candidate_gate(c, profiles, as_of=as_of, profile_sources=dataset.get("profile_sources", {}))
            for c in candidates
        }
        task_events = [e for e in events if (e["environment_profile_id"], e["task_id"]) == (environment, task_id)]
        for repeat in sorted({event["repeat_id"] for event in task_events}):
            training = sorted([e for e in task_events if e["repeat_id"] != repeat], key=lambda e: e["event_id"])
            heldout = sorted([e for e in task_events if e["repeat_id"] == repeat], key=lambda e: e["event_id"])
            feasible = sorted(route for route, gate in gates.items() if gate["status"] == "ELIGIBLE")
            status = reasons[0] if reasons else "SELECTED_OFFLINE"
            fold_reasons = list(reasons)
            if not reasons:
                for hold in ("HOLD_ELIGIBILITY_UNKNOWN", "HOLD_NOT_CALIBRATED"):
                    if any(gate["status"] == hold for gate in gates.values()):
                        status = hold
                        fold_reasons = sorted({r for gate in gates.values() if gate["status"] == hold for r in gate["reason_codes"]})
                        break
                else:
                    if not feasible:
                        status, fold_reasons = "HOLD_NO_FEASIBLE_ROUTE", ["ALL_ROUTES_INELIGIBLE"]
            predictions = predict(training, feasible) if status == "SELECTED_OFFLINE" else {}
            actual = {e["route_id"]: e["elapsed_seconds"] for e in heldout if e["route_id"] in feasible}
            if status == "SELECTED_OFFLINE" and (set(predictions) != set(feasible) or set(actual) != set(feasible)):
                status, fold_reasons = "HOLD_NOT_CALIBRATED", ["EMPIRICAL_ROUTE_SAMPLE_MISSING"]
            selected = rank(predictions) if status == "SELECTED_OFFLINE" else None
            oracle = min(actual.values()) if selected is not None else None
            baselines = {}
            for label, mode in (("always_local", "LOCAL"), ("always_direct", "DIRECT"), ("always_range", "RANGE")):
                route = next((c["route_id"] for c in candidates if c["mode"] == mode), None)
                eligible = selected is not None and route in feasible
                seconds = actual.get(route) if eligible else None
                baselines[label] = {
                    "route_id": route, "status": "EVALUATED" if eligible else "NOT_APPLICABLE",
                    "actual_seconds": seconds,
                    "relative_regret": (seconds / oracle - 1) if eligible else None,
                }
            decision = {
                "schema_version": "p0c.0.1", "policy_version": POLICY_VERSION,
                "environment_profile_id": environment, "task_id": task_id, "repeat_id": repeat,
                "evaluated_at": as_of, "status": status, "reason_codes": fold_reasons or ["EMPIRICAL_MINIMUM"],
                "candidate_gates": gates, "feasible_set": feasible,
                "predictions_seconds": predictions, "heldout_seconds": actual,
                "selected_route": selected, "predicted_seconds": predictions.get(selected),
                "heldout_actual_seconds": actual.get(selected) if selected else None,
                "oracle_seconds": oracle,
                "relative_regret": actual[selected] / oracle - 1 if selected else None,
                "baselines": baselines,
                "training_events": [e["sha256"] for e in training],
                "heldout_events": [e["sha256"] for e in heldout],
                "dataset_sha256": digest(dataset), "fixture_sha256": fixture_hash,
                "profile_hashes": {key: digest(value) for key, value in sorted(profiles.items())},
                "latency_model": "EMPIRICAL_END_TO_END_MEAN",
                "stage_terms": {name: "UNKNOWN" for name in ("stage", "network", "compute", "verify", "merge", "retry")},
                "currency": {"status": "NOT_MEASURED", "value": None},
                "energy": {"status": "NOT_MEASURED", "value": None},
                "confidence": {"status": "NOT_MEASURED", "value": None},
            }
            validate_schema(decision, "placement_decision_v01.schema.json")
            decisions.append(decision)
    selected = [d for d in decisions if d["selected_route"] is not None]
    # Audit only the offline engine. Git/PR operations are outside these counters.
    counters = {
        "PRODUCTION_DISPATCH_COUNT": 0, "EXTERNAL_NETWORK_ACTIONS": 0, "CLOUD_BILLABLE_ACTIONS": 0,
        "unauthorized_selections": sum(d["selected_route"] not in d["feasible_set"] for d in selected),
        "holdout_leakage_count": sum(bool(set(d["training_events"]) & set(d["heldout_events"])) for d in decisions),
    }
    return {
        "policy_version": POLICY_VERSION, "status": "OFFLINE_REPLAY_ONLY",
        "input_mode": dataset["input_mode"], "observations": len(events),
        "holdout_decisions": len(decisions), "selected_decisions": len(selected),
        "held_decisions": len(decisions) - len(selected), "audit": counters,
        "max_relative_regret": max((d["relative_regret"] for d in selected), default=None),
        "decisions": decisions,
    }


def run_files(input_dir: Path, output_dir: Path, trusted_key: Ed25519PublicKey, *, as_of: str) -> dict:
    """Check exact input bytes, then publish into a new, exclusive directory.

    Fixed basenames prohibit path traversal through an untrusted manifest.
    A pre-existing output directory (including a symlink) is always refused.
    Files use exclusive creation; manifest/output hashes never overwrite inputs.
    """
    manifest_bytes = (input_dir / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if set(manifest["files_sha256"]) != {"dataset.json", "fixture.txt"}:
        raise ValueError("INPUT_MANIFEST_FILE_SET_INVALID")
    sources = {name: (input_dir / name).read_bytes() for name in manifest["files_sha256"]}
    for name, content in sources.items():
        if hashlib.sha256(content).hexdigest() != manifest["files_sha256"][name]:
            raise ValueError("INPUT_HASH_MISMATCH: " + name)
    dataset = json.loads(sources["dataset.json"])
    if manifest["input_mode"] != dataset["input_mode"]:
        raise ValueError("INPUT_MODE_MISMATCH")
    result = replay(dataset, sources["fixture.txt"], trusted_key, as_of=as_of)
    output_dir.mkdir(parents=True, exist_ok=False)
    payload = dumps(result) + b"\n"
    with (output_dir / "report.json").open("xb") as stream:
        stream.write(payload)
    output_manifest = {
        "policy_version": POLICY_VERSION, "input_mode": dataset["input_mode"],
        "input_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "input_files_sha256": manifest["files_sha256"],
        "trusted_key_sha256": hashlib.sha256(trusted_key.public_bytes_raw()).hexdigest(),
        "files_sha256": {"report.json": hashlib.sha256(payload).hexdigest()},
        "provenance": "SELF_CONTAINED_HASHES_NOT_EXTERNALLY_ANCHORED",
    }
    with (output_dir / "manifest.json").open("xb") as stream:
        stream.write(dumps(output_manifest) + b"\n")
    for name in ("report.json", "manifest.json"):
        (output_dir / name).chmod(0o444)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--trusted-key", type=Path, required=True, help="operator-trusted Ed25519 public key in hex")
    parser.add_argument("--as-of", required=True, help="explicit UTC replay evaluation time")
    args = parser.parse_args(argv)
    key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(args.trusted_key.read_text().strip()))
    report = run_files(args.input_dir, args.output_dir, key, as_of=args.as_of)
    print(json.dumps({key: value for key, value in report.items() if key != "decisions"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
