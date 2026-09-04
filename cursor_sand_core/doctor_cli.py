from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import DEFAULT_DIAGNOSTIC_FEATURES
from .inventory import inventory
from .marker_doctor import MarkerState, inspect_marker_installation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cursor-sand-doctor",
        description="Read-only diagnostics for a Cursor installation tree.",
    )
    parser.add_argument("root", type=Path, help="Cursor app/resources/app root")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return non-zero unless every known diagnostic feature is healthy",
    )
    return parser


def _json_payload(root: Path) -> dict[str, object]:
    feature_report = inspect_marker_installation(root, DEFAULT_DIAGNOSTIC_FEATURES)
    bundle_inventory = inventory(root)
    return {
        "root": str(root),
        "features": json.loads(feature_report.to_json())["features"],
        "inventory": [item.to_dict() for item in bundle_inventory],
    }


def _render_text(root: Path) -> tuple[str, bool]:
    feature_report = inspect_marker_installation(root, DEFAULT_DIAGNOSTIC_FEATURES)
    bundle_inventory = inventory(root)
    lines = [f"Cursor root: {root}", "", "Features:"]
    all_features_healthy = True
    for feature in feature_report.features:
        all_features_healthy &= feature.state is MarkerState.HEALTHY
        lines.append(f"  {feature.id:<28} {feature.state.value}")
        for observation in feature.observations:
            if observation.exists:
                matched = f"{len(observation.matched)}/{len(observation.expected)} markers"
                lines.append(f"    - {observation.path}: {matched}")
            else:
                suffix = " (optional)" if observation.optional_target else ""
                lines.append(f"    - {observation.path}: target missing{suffix}")

    lines.extend(["", "Bundle inventory:"])
    for item in bundle_inventory:
        if item.exists:
            short_hash = item.sha256[:12] if item.sha256 else "-"
            lines.append(f"  OK      {item.path}  size={item.size} sha256={short_hash}…")
        else:
            lines.append(f"  MISSING {item.path}")
    return "\n".join(lines), all_features_healthy


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"error: root is not a directory: {root}", file=sys.stderr)
        return 2

    if args.as_json:
        payload = _json_payload(root)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.strict:
            states = [feature["state"] for feature in payload["features"]]
            return 0 if all(state == MarkerState.HEALTHY.value for state in states) else 1
        return 0

    rendered, all_features_healthy = _render_text(root)
    print(rendered)
    return 0 if (not args.strict or all_features_healthy) else 1


if __name__ == "__main__":
    raise SystemExit(main())
