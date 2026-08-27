from __future__ import annotations

import json
import unittest
from pathlib import Path

from dtvs.storage.r2_manifest import build_upload_manifest

ROOT = Path(__file__).resolve().parents[2]


class R2ManifestTests(unittest.TestCase):
    def test_manifest_includes_20_tasks_and_excludes_forbidden_center_files(self):
        run = ROOT / "runs" / "unit-manifest"
        (run / "center").mkdir(parents=True, exist_ok=True)
        tasks = []
        for idx in range(1, 21):
            task_id = f"DTVS-P001-T{idx:04d}"
            short = f"T{idx:04d}"
            task_dir = run / "task-inputs" / short
            task_dir.mkdir(parents=True, exist_ok=True)
            for name in ["input_with_context.mkv", "public_anchors.json", "task_bundle.json", "task_bundle.sig"]:
                (task_dir / name).write_text(f"{task_id}:{name}", encoding="utf-8")
            tasks.append({"task_id": task_id})
        (run / "center" / "task_index.json").write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
        (run / "public").mkdir(exist_ok=True)
        (run / "public" / "task_index.json").write_text("{}", encoding="utf-8")
        (run / "public" / "run_manifest.json").write_text("{}", encoding="utf-8")
        (run / "center" / "master").mkdir(parents=True, exist_ok=True)
        (run / "center" / "master" / "source_20m_video_cfr.mkv").write_text("forbidden", encoding="utf-8")
        manifest = build_upload_manifest(
            {
                "run_id": "unit-manifest",
                "local_run_root": str(run),
                "remote_prefix": "runs/unit-manifest",
                "bucket": "dtvs-pilot-assets",
                "wrangler_single_object_limit_bytes": 330301440,
            }
        )
        self.assertEqual(manifest["totals"]["tasks"], 20)
        self.assertEqual(manifest["totals"]["objects"], 82)
        serialized = json.dumps(manifest)
        self.assertNotIn("source_20m_video", serialized)
        self.assertNotIn("hidden_check", serialized)
        self.assertNotIn("private_key", serialized)


if __name__ == "__main__":
    unittest.main()

