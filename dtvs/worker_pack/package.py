from __future__ import annotations

import base64
import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dtvs.common.hashing import sha256_file
from dtvs.contracts.signing import verify_document


@dataclass(frozen=True)
class ImportedTask:
    package_path: Path
    task_dir: Path
    bundle: dict
    public_key: Ed25519PublicKey
    input_path: Path
    run_id: str | None = None


def _safe_extract(package: zipfile.ZipFile, destination: Path) -> None:
    base = destination.resolve()
    for info in package.infolist():
        target = (destination / info.filename).resolve()
        if target != base and base not in target.parents:
            raise ValueError("CORRUPT_TASK_PACKAGE_PATH_TRAVERSAL")
        if info.is_dir():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with package.open(info) as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)


def import_task_package(package_path: Path, workspace: Path) -> ImportedTask:
    if package_path.is_dir():
        raise ValueError("HANDOFF_DIRECTORY_REQUIRES_IMPORT_HANDOFF_TASKS")
    if not package_path.exists() or not zipfile.is_zipfile(package_path):
        raise ValueError("CORRUPT_TASK_PACKAGE")
    import_root = workspace / "imports" / package_path.stem
    if not import_root.exists():
        import_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package_path) as zf:
            _safe_extract(zf, import_root)
    bundle_path = import_root / "task_bundle.json"
    public_key_path = import_root / "public_key.b64"
    input_path = import_root / "input_with_context.mkv"
    for required in (bundle_path, public_key_path, input_path):
        if not required.exists():
            raise ValueError(f"CORRUPT_TASK_PACKAGE_MISSING:{required.name}")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_path.read_text(encoding="ascii").strip()))
    if not verify_document(bundle, public_key):
        raise ValueError("BUNDLE_SIGNATURE_INVALID")
    expected = bundle["input"]["sha256"]
    actual = sha256_file(input_path)
    if actual != expected:
        raise ValueError("INPUT_HASH_MISMATCH")
    return ImportedTask(package_path=package_path, task_dir=import_root, bundle=bundle, public_key=public_key, input_path=input_path)


def import_handoff_tasks(handoff_root: Path) -> tuple[dict, list[ImportedTask]]:
    if not handoff_root.is_dir():
        raise ValueError("CORRUPT_HANDOFF_PACKAGE")
    assignment_path = handoff_root / "assignment" / "offline_assignment.json"
    task_index_path = handoff_root / "control" / "task_index.json"
    if not assignment_path.exists() or not task_index_path.exists():
        raise ValueError("CORRUPT_HANDOFF_PACKAGE_MISSING_CONTROL")
    assignment = json.loads(assignment_path.read_text(encoding="utf-8"))
    task_index = json.loads(task_index_path.read_text(encoding="utf-8"))
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(task_index["public_key"]))
    if not verify_document(assignment, public_key):
        raise ValueError("ASSIGNMENT_SIGNATURE_INVALID")
    imported: list[ImportedTask] = []
    for task in assignment.get("tasks", []):
        bundle_path = handoff_root / task["bundle_path"]
        input_path = handoff_root / task["input_path"]
        anchors_path = handoff_root / task["anchors_path"]
        sig_path = handoff_root / task["bundle_signature_path"]
        for required in (bundle_path, input_path, anchors_path, sig_path):
            if not required.exists():
                raise ValueError(f"CORRUPT_HANDOFF_TASK_MISSING:{required}")
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        if bundle["task_id"] != task["task_id"]:
            raise ValueError("HANDOFF_TASK_ID_MISMATCH")
        if not verify_document(bundle, public_key):
            raise ValueError("BUNDLE_SIGNATURE_INVALID")
        if sha256_file(input_path) != task["input_sha256"] or task["input_sha256"] != bundle["input"]["sha256"]:
            raise ValueError("INPUT_HASH_MISMATCH")
        imported.append(
            ImportedTask(
                package_path=handoff_root,
                task_dir=bundle_path.parent,
                bundle=bundle,
                public_key=public_key,
                input_path=input_path,
                run_id=assignment["run_id"],
            )
        )
    if len(imported) != assignment.get("expected_tasks"):
        raise ValueError("HANDOFF_TASK_COUNT_MISMATCH")
    return assignment, imported
