from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


class TransactionError(RuntimeError):
    pass


@dataclass
class _Entry:
    path: Path
    original: bytes
    updated: bytes


@dataclass
class FileTransaction:
    entries: list[_Entry] = field(default_factory=list)

    def stage(self, path: Path, updated: bytes) -> None:
        original = path.read_bytes()
        self.entries.append(_Entry(path=path, original=original, updated=updated))

    def commit(self) -> None:
        written: list[_Entry] = []
        try:
            for entry in self.entries:
                self._atomic_write(entry.path, entry.updated)
                written.append(entry)
        except Exception as exc:  # pragma: no cover - recovery path
            for entry in reversed(written):
                self._atomic_write(entry.path, entry.original)
            raise TransactionError(str(exc)) from exc

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            shutil.copymode(path, tmp_name) if path.exists() else None
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
