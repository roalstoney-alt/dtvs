from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_document(document: dict[str, Any], schema_path: Path) -> None:
    Draft202012Validator(load_schema(schema_path)).validate(document)

