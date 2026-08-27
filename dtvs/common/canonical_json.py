from __future__ import annotations

import json
from typing import Any


def dumps(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_bytes(payload: bytes) -> Any:
    return json.loads(payload.decode("utf-8"))

