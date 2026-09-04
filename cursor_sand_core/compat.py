from __future__ import annotations

from collections.abc import Sequence

from .version import VERSION


def run_legacy(argv: Sequence[str] | None = None) -> int:
    """Run the frozen 1.5.8 runtime without changing its patch behavior."""
    from . import legacy_runtime

    # Report the package version while leaving all runtime constants/patch logic intact.
    legacy_runtime.TOOL_VERSION = VERSION
    return legacy_runtime.main(argv)
