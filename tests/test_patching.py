from cursor_sand_core.patching import (
    PatchSpec,
    PatchState,
    apply_patch,
    inspect_patch,
    restore_patch,
)


def _spec() -> PatchSpec:
    return PatchSpec(
        id="demo",
        description="demo patch",
        required=True,
        detect_original=lambda content: content.count("ORIGINAL"),
        detect_patched=lambda content: content.count("PATCHED"),
        apply=lambda content: content.replace("ORIGINAL", "PATCHED", 1),
        restore=lambda content: content.replace("PATCHED", "ORIGINAL", 1),
    )


def test_apply_is_idempotent() -> None:
    spec = _spec()
    first, result = apply_patch(spec, "a ORIGINAL b")
    second, second_result = apply_patch(spec, first)
    assert result.after is PatchState.PATCHED
    assert second == first
    assert second_result.changed is False


def test_restore_round_trip() -> None:
    spec = _spec()
    original = "a ORIGINAL b"
    patched, _ = apply_patch(spec, original)
    restored, result = restore_patch(spec, patched)
    assert restored == original
    assert result.after is PatchState.ORIGINAL


def test_ambiguous_state_is_not_modified() -> None:
    spec = _spec()
    content = "ORIGINAL PATCHED"
    assert inspect_patch(spec, content) is PatchState.AMBIGUOUS
    updated, result = apply_patch(spec, content)
    assert updated == content
    assert result.changed is False
