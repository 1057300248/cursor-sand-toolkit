from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_TARGETS: tuple[str, ...] = (
    "out/main.js",
    "out/vs/workbench/api/worker/extensionHostWorkerMain.js",
    "out/vs/workbench/api/node/extensionHostProcess.js",
    "out/vs/workbench/workbench.glass.main.js",
    "out/vs/workbench/workbench.desktop.main.js",
    "extensions/cursor-local-agent-runtime/dist/main.js",
    "extensions/cursor-agent-host/dist/main.js",
    "extensions/cursor-agent-exec/dist/main.js",
    "extensions/cursor-agent-host/dist/657.js",
    "extensions/cursor-agent-host/dist/675.js",
)


@dataclass(frozen=True)
class InventoryItem:
    path: str
    exists: bool
    size: int | None
    sha256: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path, targets: Iterable[str] = DEFAULT_TARGETS) -> tuple[InventoryItem, ...]:
    result: list[InventoryItem] = []
    for relative in targets:
        path = root.joinpath(*relative.split("/"))
        if not path.is_file():
            result.append(InventoryItem(relative, False, None, None))
            continue
        stat = path.stat()
        result.append(InventoryItem(relative, True, stat.st_size, sha256_file(path)))
    return tuple(result)
