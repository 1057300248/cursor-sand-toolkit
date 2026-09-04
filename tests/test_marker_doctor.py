from pathlib import Path

from cursor_sand_core.marker_doctor import (
    MarkerFeature,
    MarkerRequirement,
    MarkerState,
    inspect_marker_feature,
)


def _write(root: Path, relative: str, content: str) -> None:
    path = root.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_marker_feature_healthy(tmp_path: Path) -> None:
    _write(tmp_path, "out/a.js", "before /*ONE*/ middle /*TWO*/ after")
    feature = MarkerFeature(
        "demo",
        "demo feature",
        (MarkerRequirement("out/a.js", ("/*ONE*/", "/*TWO*/")),),
        required=True,
    )
    result = inspect_marker_feature(tmp_path, feature)
    assert result.state is MarkerState.HEALTHY
    assert result.healthy


def test_marker_feature_missing_marker(tmp_path: Path) -> None:
    _write(tmp_path, "out/a.js", "/*ONE*/")
    feature = MarkerFeature(
        "demo",
        "demo feature",
        (MarkerRequirement("out/a.js", ("/*ONE*/", "/*TWO*/")),),
    )
    result = inspect_marker_feature(tmp_path, feature)
    assert result.state is MarkerState.MISSING


def test_marker_feature_partial_when_required_target_missing(tmp_path: Path) -> None:
    _write(tmp_path, "out/a.js", "/*ONE*/")
    feature = MarkerFeature(
        "demo",
        "demo feature",
        (
            MarkerRequirement("out/a.js", ("/*ONE*/",)),
            MarkerRequirement("out/b.js", ("/*TWO*/",)),
        ),
    )
    result = inspect_marker_feature(tmp_path, feature)
    assert result.state is MarkerState.PARTIAL


def test_optional_target_can_be_absent(tmp_path: Path) -> None:
    _write(tmp_path, "out/a.js", "/*ONE*/")
    feature = MarkerFeature(
        "demo",
        "demo feature",
        (
            MarkerRequirement("out/a.js", ("/*ONE*/",)),
            MarkerRequirement("out/optional.js", ("/*TWO*/",), optional_target=True),
        ),
    )
    result = inspect_marker_feature(tmp_path, feature)
    assert result.state is MarkerState.HEALTHY
