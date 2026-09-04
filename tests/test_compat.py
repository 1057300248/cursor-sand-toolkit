from cursor_sand_core import legacy_runtime
from cursor_sand_core.version import LEGACY_RUNTIME_VERSION


def test_legacy_runtime_is_importable() -> None:
    assert callable(legacy_runtime.main)
    assert legacy_runtime.TOOL_VERSION == LEGACY_RUNTIME_VERSION
