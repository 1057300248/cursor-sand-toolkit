from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class PatchState(str, Enum):
    ORIGINAL = "original"
    PATCHED = "patched"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"


@dataclass(frozen=True)
class PatchSpec:
    id: str
    description: str
    required: bool
    detect_original: Callable[[str], int]
    detect_patched: Callable[[str], int]
    apply: Callable[[str], str]
    restore: Callable[[str], str]


@dataclass(frozen=True)
class PatchResult:
    patch_id: str
    before: PatchState
    after: PatchState
    changed: bool


def inspect_patch(spec: PatchSpec, content: str) -> PatchState:
    original = spec.detect_original(content)
    patched = spec.detect_patched(content)
    if original == 1 and patched == 0:
        return PatchState.ORIGINAL
    if original == 0 and patched == 1:
        return PatchState.PATCHED
    if original == 0 and patched == 0:
        return PatchState.MISSING
    return PatchState.AMBIGUOUS


def apply_patch(spec: PatchSpec, content: str) -> tuple[str, PatchResult]:
    before = inspect_patch(spec, content)
    if before is PatchState.PATCHED:
        return content, PatchResult(spec.id, before, before, False)
    if before is not PatchState.ORIGINAL:
        return content, PatchResult(spec.id, before, before, False)

    updated = spec.apply(content)
    after = inspect_patch(spec, updated)
    changed = updated != content
    return updated, PatchResult(spec.id, before, after, changed)


def restore_patch(spec: PatchSpec, content: str) -> tuple[str, PatchResult]:
    before = inspect_patch(spec, content)
    if before is PatchState.ORIGINAL:
        return content, PatchResult(spec.id, before, before, False)
    if before is not PatchState.PATCHED:
        return content, PatchResult(spec.id, before, before, False)

    updated = spec.restore(content)
    after = inspect_patch(spec, updated)
    changed = updated != content
    return updated, PatchResult(spec.id, before, after, changed)
