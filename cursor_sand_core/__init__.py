"""Cursor Sand Toolkit 1.6 engineering package.

New code lives in focused modules for command routing, diagnostics, fingerprints,
patch orchestration and transactional file updates. The unchanged 1.5.8 executor
is retained as a compatibility runtime while migration proceeds feature by feature.
"""

from .doctor import DoctorReport, inspect_installation
from .inventory import InventoryItem, inventory, sha256_file
from .marker_doctor import (
    MarkerDoctorReport,
    MarkerFeature,
    MarkerFeatureResult,
    MarkerObservation,
    MarkerRequirement,
    MarkerState,
    inspect_marker_feature,
    inspect_marker_installation,
)
from .patching import PatchResult, PatchSpec, PatchState, apply_patch, inspect_patch
from .profiles import BuildProfile, Fingerprint, ProfileMatch, match_profile
from .transaction import FileTransaction, TransactionError
from .version import LEGACY_RUNTIME_VERSION, TOOL_NAME, VERSION

__version__ = VERSION

__all__ = [
    "BuildProfile",
    "DoctorReport",
    "FileTransaction",
    "Fingerprint",
    "InventoryItem",
    "LEGACY_RUNTIME_VERSION",
    "MarkerDoctorReport",
    "MarkerFeature",
    "MarkerFeatureResult",
    "MarkerObservation",
    "MarkerRequirement",
    "MarkerState",
    "PatchResult",
    "PatchSpec",
    "PatchState",
    "ProfileMatch",
    "TOOL_NAME",
    "TransactionError",
    "VERSION",
    "apply_patch",
    "inspect_installation",
    "inspect_marker_feature",
    "inspect_marker_installation",
    "inspect_patch",
    "inventory",
    "match_profile",
    "sha256_file",
]
