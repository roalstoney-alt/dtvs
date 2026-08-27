from __future__ import annotations

import argparse
import json
from pathlib import Path

from dtvs.worker_pack.runtime import doctor, export_run, run_task, submit_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dtvs-worker")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    run = sub.add_parser("run")
    run.add_argument("--package", required=True)
    run.add_argument("--workspace", required=True)
    export = sub.add_parser("export")
    export.add_argument("--workspace", required=True)
    export.add_argument("--run-id", required=True)
    export.add_argument("--destination", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--workspace", required=True)
    submit.add_argument("--run-id", required=True)
    submit.add_argument("--assignment", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor(Path.cwd())
        elif args.command == "run":
            result = run_task(Path(args.package), Path(args.workspace))
        elif args.command == "export":
            result = export_run(Path(args.workspace), args.run_id, Path(args.destination))
        else:
            result = submit_run(Path(args.workspace), args.run_id, Path(args.assignment))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) is not False else 2
    except Exception as exc:
        print(json.dumps({"state": "FAILED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

