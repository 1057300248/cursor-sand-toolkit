from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path


class MarkerState(str, Enum):
    HEALTHY = "healthy"
    PARTIAL = "partial"
    MISSING = "missing"
    TARGET_MISSING = "target-missing"


@dataclass(frozen=True)
class MarkerRequirement:
    path: str
    markers: tuple[str, ...]
    require_all: bool = True
    optional_target: bool = False


@dataclass(frozen=True)
class MarkerFeature:
    id: str
    description: str
    requirements: tuple[MarkerRequirement, ...]
    required: bool = False


@dataclass(frozen=True)
class MarkerObservation:
    path: str
    exists: bool
    matched: tuple[str, ...]
    expected: tuple[str, ...]
    healthy: bool
    optional_target: bool


@dataclass(frozen=True)
class MarkerFeatureResult:
    id: str
    description: str
    state: MarkerState
    required: bool
    observations: tuple[MarkerObservation, ...]

    @property
    def healthy(self) -> bool:
        return self.state is MarkerState.HEALTHY


@dataclass(frozen=True)
class MarkerDoctorReport:
    root: str
    healthy: bool
    features: tuple[MarkerFeatureResult, ...]

    def to_json(self) -> str:
        payload = asdict(self)
        for feature in payload["features"]:
            feature["state"] = feature["state"].value
        return json.dumps(payload, ensure_ascii=False, indent=2)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def inspect_marker_feature(root: Path, feature: MarkerFeature) -> MarkerFeatureResult:
    observations: list[MarkerObservation] = []
    required_targets_seen = 0
    required_targets_healthy = 0

    for requirement in feature.requirements:
        path = root.joinpath(*requirement.path.split("/"))
        if not path.is_file():
            observations.append(
                MarkerObservation(
                    requirement.path,
                    False,
                    (),
                    requirement.markers,
                    requirement.optional_target,
                    requirement.optional_target,
                )
            )
            continue

        content = _read_text(path)
        matched = tuple(marker for marker in requirement.markers if marker in content)
        healthy = (
            len(matched) == len(requirement.markers)
            if requirement.require_all
            else bool(matched)
        )
        observations.append(
            MarkerObservation(
                requirement.path,
                True,
                matched,
                requirement.markers,
                healthy,
                requirement.optional_target,
            )
        )
        if not requirement.optional_target:
            required_targets_seen += 1
            required_targets_healthy += int(healthy)

    required_count = sum(not item.optional_target for item in feature.requirements)
    if required_targets_seen == 0 and required_count:
        state = MarkerState.TARGET_MISSING
    elif required_targets_seen < required_count:
        state = MarkerState.PARTIAL
    elif required_targets_healthy == required_count:
        state = MarkerState.HEALTHY
    elif required_targets_healthy == 0:
        state = MarkerState.MISSING
    else:
        state = MarkerState.PARTIAL

    return MarkerFeatureResult(
        feature.id,
        feature.description,
        state,
        feature.required,
        tuple(observations),
    )


def inspect_marker_installation(
    root: Path,
    features: Iterable[MarkerFeature],
) -> MarkerDoctorReport:
    results = tuple(inspect_marker_feature(root, feature) for feature in features)
    healthy = all(result.healthy for result in results if result.required)
    return MarkerDoctorReport(str(root), healthy, results)
