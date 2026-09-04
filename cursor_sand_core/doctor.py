from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .patching import PatchSpec, PatchState, inspect_patch


@dataclass(frozen=True)
class DoctorItem:
    patch_id: str
    state: PatchState
    required: bool
    healthy: bool


@dataclass(frozen=True)
class DoctorReport:
    root: str
    healthy: bool
    items: list[DoctorItem]

    def to_json(self) -> str:
        payload = asdict(self)
        payload["items"] = [
            {**asdict(item), "state": item.state.value} for item in self.items
        ]
        return json.dumps(payload, ensure_ascii=False, indent=2)


def inspect_installation(
    root: Path,
    content: str,
    specs: Iterable[PatchSpec],
) -> DoctorReport:
    items: list[DoctorItem] = []
    for spec in specs:
        state = inspect_patch(spec, content)
        healthy = state in {PatchState.ORIGINAL, PatchState.PATCHED}
        if spec.required:
            healthy = state is PatchState.PATCHED
        items.append(DoctorItem(spec.id, state, spec.required, healthy))
    return DoctorReport(str(root), all(item.healthy for item in items), items)
