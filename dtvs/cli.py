from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dtvs")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)
    if args.version:
        print("dtvs 0.2.2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

