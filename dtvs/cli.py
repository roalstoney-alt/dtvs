from __future__ import annotations

import argparse
from pathlib import Path

from dtvs.pilot import run_fixture_pilot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dtvs")
    parser.add_argument("--version", action="store_true")
    sub = parser.add_subparsers(dest="command")
    pilot = sub.add_parser("pilot")
    pilot_sub = pilot.add_subparsers(dest="pilot_command")
    run = pilot_sub.add_parser("run")
    run.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    if args.version:
        print("dtvs 0.2.2")
        return 0
    if args.command == "pilot" and args.pilot_command == "run":
        summary = run_fixture_pilot(Path(args.config), Path("runs"))
        print(summary["run_id"])
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
