"""Real NCNN/Vulkan executor used by the Windows pilot handoff.

This module never falls back to the fixture executor.  Windows-only process
execution is kept behind a small, testable command and validation boundary.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from dtvs.common.hashing import sha256_file
try:
    from dtvs.contracts.validation import validate_document
except ModuleNotFoundError as exc:
    if exc.name != "jsonschema":
        raise
    validate_document = None


@dataclass(frozen=True)
class NcnnArtifacts:
    executable: Path
    param: Path
    bin: Path
    executable_sha256: str
    param_sha256: str
    bin_sha256: str


def build_realesrgan_command(
    executable: Path,
    input_path: Path,
    output_path: Path,
    model_dir: Path,
    *,
    model: str = "realesrgan-x4plus",
    scale: int = 4,
    tile: int | None = 64,
) -> list[str]:
    command = [str(executable), "-i", str(input_path), "-o", str(output_path), "-n", model, "-s", str(scale), "-m", str(model_dir), "-v"]
    if tile is not None:
        command.extend(["-t", str(tile)])
    return command


def _require_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label}_MISSING")
    if sha256_file(path) != expected:
        raise ValueError(f"{label}_HASH_MISMATCH")


def _validate_bundle_fallback(bundle: dict[str, Any]) -> None:
    required = {"schema_version", "task_id", "bundle_version", "asset_id", "core", "context", "input", "execution", "output", "lease", "verification", "signature"}
    if bundle.get("schema_version") != "0.2.2" or not required.issubset(bundle):
        raise ValueError("TASK_BUNDLE_SCHEMA_INVALID")
    if bundle.get("execution", {}).get("execution_mode") != "real_render":
        raise ValueError("REAL_RENDER_MODE_REQUIRED")
    if bundle.get("execution", {}).get("backend") != "ncnn_vulkan":
        raise ValueError("UNSUPPORTED_PIPELINE")
    for section in ("core", "context"):
        value = bundle[section]
        if not isinstance(value.get("start_frame"), int) or not isinstance(value.get("end_frame_exclusive"), int) or value["end_frame_exclusive"] <= value["start_frame"]:
            raise ValueError("TASK_BUNDLE_SCHEMA_INVALID")


def _ffprobe(path: Path, runner: Callable[..., subprocess.CompletedProcess[str]]) -> dict[str, Any]:
    if shutil.which("ffprobe") is None:
        raise ValueError("FFPROBE_REQUIRED")
    result = runner(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise ValueError("OUTPUT_DECODE_FAILED")
    return json.loads(result.stdout or "{}")


def execute_realesrgan_ncnn(
    bundle: dict[str, Any],
    attempt_dir: Path,
    *,
    input_path: Path,
    command_input_path: Path | None = None,
    artifacts: NcnnArtifacts,
    model_dir: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Execute one real-render bundle and write auditable attempt evidence."""
    if bundle.get("execution", {}).get("execution_mode") != "real_render":
        raise ValueError("REAL_RENDER_MODE_REQUIRED")
    if bundle.get("execution", {}).get("backend") != "ncnn_vulkan":
        raise ValueError("UNSUPPORTED_PIPELINE")
    if validate_document is None:
        _validate_bundle_fallback(bundle)
    else:
        validate_document(bundle, Path(__file__).resolve().parents[2] / "schemas/task_bundle_v022.schema.json")
    expected_input = bundle["input"]["sha256"].removeprefix("sha256:")
    if sha256_file(input_path) != expected_input:
        raise ValueError("INPUT_HASH_MISMATCH")
    _require_hash(artifacts.executable, artifacts.executable_sha256, "EXECUTABLE")
    _require_hash(artifacts.param, artifacts.param_sha256, "MODEL_PARAM")
    _require_hash(artifacts.bin, artifacts.bin_sha256, "MODEL_BIN")
    attempt_dir.mkdir(parents=True, exist_ok=True)
    output_path = attempt_dir / "output"
    command = build_realesrgan_command(artifacts.executable, command_input_path or input_path, output_path, model_dir, tile=bundle.get("execution", {}).get("tile", 64))
    started = datetime.now(timezone.utc).isoformat()
    process = runner(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    ended = datetime.now(timezone.utc).isoformat()
    (attempt_dir / "command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
    (attempt_dir / "stdout.log").write_text(process.stdout or "", encoding="utf-8")
    (attempt_dir / "stderr.log").write_text(process.stderr or "", encoding="utf-8")
    if process.returncode != 0:
        raise RuntimeError("REAL_ESRGAN_PROCESS_FAILED")
    output_files = [p for p in output_path.rglob("*") if p.is_file()] if output_path.is_dir() else [output_path]
    if not output_files:
        raise RuntimeError("OUTPUT_NOT_FOUND")
    output_hashes = [{"path": str(p.relative_to(attempt_dir)), "sha256": sha256_file(p), "bytes": p.stat().st_size} for p in sorted(output_files)]
    probe = _ffprobe(output_files[0], runner)
    video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
    expected_width = bundle.get("output", {}).get("width")
    expected_height = bundle.get("output", {}).get("height")
    if expected_width and expected_height and (video.get("width"), video.get("height")) != (expected_width, expected_height):
        raise RuntimeError("OUTPUT_DIMENSIONS_MISMATCH")
    manifest = {
        "schema_version": "0.2.2", "task_id": bundle["task_id"], "attempt_id": attempt_dir.name,
        "backend": "ncnn_vulkan", "execution_mode": "real_render", "started_at": started, "ended_at": ended,
        "actual_command": command, "exit_code": process.returncode, "output_hashes": output_hashes,
        "output_probe": probe, "worker_state": "READY_FOR_RETURN", "fixture_call_count": 0,
    }
    (attempt_dir / "attempt_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (attempt_dir / "checkpoint.json").write_text(json.dumps({"task_id": bundle["task_id"], "state": "READY_FOR_RETURN", "output_hashes": output_hashes}, indent=2) + "\n", encoding="utf-8")
    return manifest


def execute_task(bundle: dict[str, Any], attempt_dir: Path, **kwargs: Any) -> dict[str, Any]:
    execution = bundle.get("execution", {})
    if execution.get("execution_mode") == "real_render" and execution.get("backend") == "fixture_test":
        raise ValueError("FIXTURE_FORBIDDEN_FOR_REAL_TASK")
    if execution.get("execution_mode") == "fixture_test":
        from dtvs.worker.executor import execute_fixture
        return execute_fixture(bundle, attempt_dir, attempt_id=attempt_dir.name)
    if execution.get("execution_mode") == "real_render" and execution.get("backend") == "ncnn_vulkan":
        return execute_realesrgan_ncnn(bundle, attempt_dir, **kwargs)
    if execution.get("execution_mode") == "real_render":
        raise ValueError("UNSUPPORTED_PIPELINE")
    raise ValueError("EXECUTION_MODE_REQUIRED")
