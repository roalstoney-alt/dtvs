#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    downloads = Path.home() / "Downloads"
    files = sorted(downloads.glob("*.webm")) + sorted(downloads.glob("*.WEBM"))
    result = [
        {"name": path.name, "bytes": path.stat().st_size, "modified_time": path.stat().st_mtime}
        for path in files
        if path.is_file()
    ]
    print(json.dumps({"count": len(result), "files": result}, ensure_ascii=False, indent=2))
    return 0 if len(result) <= 1 else 2


if __name__ == "__main__":
    raise SystemExit(main())

