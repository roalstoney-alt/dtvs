from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

from dtvs.common.hashing import sha256_file
from dtvs.contracts.models import FrameRange, TaskBundle
from dtvs.contracts.signing import generate_private_key, public_key_bytes, sign_document
from dtvs.worker_pack.runtime import doctor, export_run, run_task, submit_run

ROOT = Path(__file__).resolve().parents[2]


def make_task_package(base: Path, *, tamper_signature: bool = False, low_score: bool = False) -> Path:
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    input_file = base / "input_with_context.mkv"
    input_file.write_text("fixture input", encoding="utf-8")
    key = generate_private_key()
    bundle = TaskBundle(
        task_id="DTVS-P001-T0001",
        bundle_version=1,
        asset_id="sha256:" + "a" * 64,
        core=FrameRange(0, 1440),
        context=FrameRange(0, 1456),
        input={"path_or_object_key": "input_with_context.mkv", "sha256": sha256_file(input_file)},
        execution={
            "worker_pack_version": "0.1.0",
            "pipeline_id": "restoration_realesrgan_v1",
            "model_sha256": "c" * 64,
            "parameters_sha256": "d" * 64,
            "random_seed": 20260827,
        },
        output={"width": 3840, "height": 2160, "fps_num": 24, "fps_den": 1, "expected_core_frames": 1440},
        lease={"expires_at": "2026-08-28T00:00:00+00:00", "checkpoint_frames": 120},
        verification={"upload_threshold": 90, "minimum_component_score": 70},
    ).to_dict()
    signed = sign_document(bundle, key, "pilot-local-001")
    if tamper_signature:
        signed["core"]["end_frame_exclusive"] = 1439
    (base / "task_bundle.json").write_text(json.dumps(signed, ensure_ascii=False), encoding="utf-8")
    (base / "task_bundle.sig").write_text(signed["signature"]["value"], encoding="ascii")
    (base / "public_key.b64").write_text(base64.b64encode(public_key_bytes(key)).decode("ascii"), encoding="ascii")
    (base / "public_anchors.json").write_text(json.dumps({"task_id": signed["task_id"]}), encoding="utf-8")
    package = base / ("task package low.zip" if low_score else "task package.zip")
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ["task_bundle.json", "task_bundle.sig", "public_key.b64", "public_anchors.json", "input_with_context.mkv"]:
            zf.write(base / name, name)
    return package


def make_handoff_directory(base: Path) -> Path:
    if base.exists():
        shutil.rmtree(base)
    key = generate_private_key()
    tasks = []
    handoff = base / "DTVS-P001-OFFLINE-HANDOFF"
    (handoff / "assignment").mkdir(parents=True)
    (handoff / "control").mkdir()
    for idx in range(1, 21):
        task_id = f"DTVS-P001-T{idx:04d}"
        short = f"T{idx:04d}"
        task_dir = handoff / "task-inputs" / short
        task_dir.mkdir(parents=True)
        input_file = task_dir / "input_with_context.mkv"
        input_file.write_text(f"fixture input {idx}", encoding="utf-8")
        bundle = TaskBundle(
            task_id=task_id,
            bundle_version=1,
            asset_id="sha256:" + "a" * 64,
            core=FrameRange((idx - 1) * 10, idx * 10),
            context=FrameRange(max(0, (idx - 1) * 10 - 1), idx * 10 + 1),
            input={"path_or_object_key": f"task-inputs/{short}/input_with_context.mkv", "sha256": sha256_file(input_file)},
            execution={
                "worker_pack_version": "0.1.0",
                "pipeline_id": "restoration_realesrgan_v1",
                "model_sha256": "c" * 64,
                "parameters_sha256": "d" * 64,
                "random_seed": 20260827,
            },
            output={"width": 3840, "height": 2160, "fps_num": 24, "fps_den": 1, "expected_core_frames": 10},
            lease={"expires_at": "2026-08-28T00:00:00+00:00", "checkpoint_frames": 120},
            verification={"upload_threshold": 90, "minimum_component_score": 70},
        ).to_dict()
        signed = sign_document(bundle, key, "pilot-local-001")
        (task_dir / "task_bundle.json").write_text(json.dumps(signed, ensure_ascii=False), encoding="utf-8")
        (task_dir / "task_bundle.sig").write_text(signed["signature"]["value"], encoding="ascii")
        (task_dir / "public_anchors.json").write_text(json.dumps({"task_id": task_id}), encoding="utf-8")
        tasks.append(
            {
                "task_id": task_id,
                "input_path": f"task-inputs/{short}/input_with_context.mkv",
                "bundle_path": f"task-inputs/{short}/task_bundle.json",
                "bundle_signature_path": f"task-inputs/{short}/task_bundle.sig",
                "anchors_path": f"task-inputs/{short}/public_anchors.json",
                "input_sha256": sha256_file(input_file),
                "input_bytes": input_file.stat().st_size,
            }
        )
    (handoff / "control" / "task_index.json").write_text(
        json.dumps({"schema_version": "0.2.2", "run_id": "DTVS-P001-TEST", "public_key": base64.b64encode(public_key_bytes(key)).decode("ascii"), "tasks": tasks}),
        encoding="utf-8",
    )
    assignment = {
        "schema_version": "0.2.2",
        "assignment_version": 1,
        "transport_mode": "OFFLINE_MANUAL",
        "run_id": "DTVS-P001-TEST",
        "worker_pack_version": "0.1.0",
        "expected_tasks": 20,
        "network_required": False,
        "result_state_limit": "READY_FOR_RETURN",
        "task_index_path": "control/task_index.json",
        "created_at": "2026-08-27T00:00:00+00:00",
        "tasks": tasks,
    }
    signed_assignment = sign_document(assignment, key, "pilot-local-001")
    (handoff / "assignment" / "offline_assignment.json").write_text(json.dumps(signed_assignment, ensure_ascii=False), encoding="utf-8")
    return handoff


class WorkerPackCliTests(unittest.TestCase):
    def test_doctor_success_and_failure(self):
        ok = doctor(ROOT / "runs" / "worker-pack doctor ok")
        self.assertTrue(ok["ok"])
        fail = doctor(ROOT / "runs" / "worker-pack doctor fail", require_model=True)
        self.assertFalse(fail["ok"])

    def test_corrupt_task_package_rejected(self):
        bad = ROOT / "runs" / "worker-pack" / "bad.zip"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("not zip", encoding="utf-8")
        with self.assertRaises(ValueError):
            run_task(bad, ROOT / "runs" / "worker-pack workspace")

    def test_bundle_signature_failure_rejected(self):
        package = make_task_package(ROOT / "runs" / "worker-pack sigfail", tamper_signature=True)
        with self.assertRaises(ValueError):
            run_task(package, ROOT / "runs" / "worker-pack sig workspace")

    def test_run_first_interrupt_resume_and_skip_completed_with_space_paths(self):
        package = make_task_package(ROOT / "runs" / "worker-pack package with spaces")
        workspace = ROOT / "runs" / "worker-pack workspace with spaces"
        if workspace.exists():
            shutil.rmtree(workspace)
        interrupted = run_task(package, workspace, simulate_interrupt=True)
        self.assertEqual(interrupted["worker_state"], "INTERRUPTED")
        resumed = run_task(package, workspace)
        self.assertTrue(resumed["ready_for_return"])
        self.assertTrue(resumed["resumed"])
        self.assertNotIn("UPLOADED", json.dumps(resumed))
        skipped = run_task(package, workspace)
        self.assertEqual(skipped["action"], "SKIPPED_COMPLETED")
        self.assertNotIn("ACCEPTED", json.dumps(skipped))

    def test_local_low_score_ready_for_return_without_acceptance(self):
        package = make_task_package(ROOT / "runs" / "worker-pack lowscore", low_score=True)
        workspace = ROOT / "runs" / "worker-pack lowscore workspace"
        if workspace.exists():
            shutil.rmtree(workspace)
        result = run_task(package, workspace, force_low_score=True)
        self.assertTrue(result["ready_for_return"])
        self.assertFalse(result["local_qc"]["upload_allowed"])
        self.assertIn("LOCAL_SCORE_BELOW_THRESHOLD", result["local_qc"]["reason_codes"])
        self.assertNotIn("ACCEPTED", json.dumps(result))

    def test_export_offline_zip_and_submit_downgrades_without_network_target(self):
        package = make_task_package(ROOT / "runs" / "worker-pack export")
        workspace = ROOT / "runs" / "worker-pack export workspace"
        if workspace.exists():
            shutil.rmtree(workspace)
        result = run_task(package, workspace)
        exported = export_run(workspace, result["run_id"], ROOT / "runs" / "worker-pack export destination")
        self.assertTrue(Path(exported["zip_path"]).exists())
        assignment = ROOT / "runs" / "worker-pack empty assignment.json"
        assignment.write_text("{}", encoding="utf-8")
        submitted = submit_run(workspace, result["run_id"], assignment)
        self.assertEqual(submitted["state"], "OFFLINE_RETURN_READY")

    def test_public_cli_and_double_click_cmd_entry(self):
        package = make_task_package(ROOT / "runs" / "worker-pack cli")
        workspace = ROOT / "runs" / "worker-pack cli workspace"
        if workspace.exists():
            shutil.rmtree(workspace)
        cp = subprocess.run(
            [sys.executable, "dtvs_worker_cli.py", "run", "--package", str(package), "--workspace", str(workspace)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        self.assertIn("READY_FOR_RETURN", cp.stdout)
        cmd = (ROOT / "START_DTVS_WORKER.cmd").read_text(encoding="utf-8")
        self.assertIn("Task package path", cmd)
        self.assertIn("dtvs-worker.ps1", cmd)

    def test_handoff_directory_run_processes_20_tasks_and_skips_on_second_run(self):
        handoff = make_handoff_directory(ROOT / "runs" / "worker-pack handoff")
        workspace = ROOT / "runs" / "worker-pack handoff workspace"
        if workspace.exists():
            shutil.rmtree(workspace)
        result = run_task(handoff, workspace)
        self.assertEqual(result["task_count"], 20)
        self.assertEqual(result["ready_for_return"], 20)
        self.assertEqual(result["worker_state"], "READY_FOR_RETURN")
        self.assertNotIn("ACCEPTED", json.dumps(result))
        skipped = run_task(handoff, workspace)
        self.assertEqual(skipped["ready_for_return"], 20)
        self.assertTrue(all(item.get("action") == "SKIPPED_COMPLETED" for item in skipped["results"]))


if __name__ == "__main__":
    unittest.main()
