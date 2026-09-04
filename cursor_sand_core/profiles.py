from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Fingerprint:
    path: str
    sha256: str

    @classmethod
    def from_file(cls, root: Path, relative_path: str) -> Fingerprint:
        data = (root / relative_path).read_bytes()
        return cls(relative_path, hashlib.sha256(data).hexdigest())


@dataclass(frozen=True)
class BuildProfile:
    name: str
    cursor_version: str
    fingerprints: Mapping[str, str]


@dataclass(frozen=True)
class ProfileMatch:
    profile: BuildProfile | None
    matched: int
    total: int
    exact: bool


def match_profile(observed: Mapping[str, str], profiles: list[BuildProfile]) -> ProfileMatch:
    best: ProfileMatch | None = None
    for profile in profiles:
        total = len(profile.fingerprints)
        matched = sum(
            1 for path, digest in profile.fingerprints.items() if observed.get(path) == digest
        )
        current = ProfileMatch(profile, matched, total, total > 0 and matched == total)
        if best is None or current.matched > best.matched:
            best = current
    return best or ProfileMatch(None, 0, 0, False)
