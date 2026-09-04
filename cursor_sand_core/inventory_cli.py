from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .inventory import inventory


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cursor-sand-toolkit inventory",
        description="List known Cursor bundle targets and their SHA-256 fingerprints.",
    )
    parser.add_argument("root", type=Path, help="Cursor app/resources/app root")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"error: root is not a directory: {root}", file=sys.stderr)
        return 2

    items = inventory(root)
    if args.as_json:
        print(json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2))
        return 0

    print(f"Cursor root: {root}")
    for item in items:
        if item.exists:
            digest = item.sha256 or "-"
            print(f"OK      {item.path}  size={item.size} sha256={digest}")
        else:
            print(f"MISSING {item.path}")
    return 0
