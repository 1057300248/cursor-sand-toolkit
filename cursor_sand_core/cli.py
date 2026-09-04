from __future__ import annotations

import sys
from collections.abc import Sequence

from . import compat
from .doctor_cli import main as doctor_main
from .inventory_cli import main as inventory_main
from .version import LEGACY_RUNTIME_VERSION, TOOL_NAME, VERSION


def _print_version() -> int:
    print(f"{TOOL_NAME} {VERSION} (compat runtime {LEGACY_RUNTIME_VERSION})")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"--version", "-V", "version"}:
        return _print_version()
    if args and args[0] == "doctor":
        return doctor_main(args[1:])
    if args and args[0] == "inventory":
        return inventory_main(args[1:])
    return compat.run_legacy(args)


def entrypoint() -> None:
    raise SystemExit(main())
