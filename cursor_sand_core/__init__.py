"""Reusable engineering primitives for Cursor Sand Toolkit.

This package intentionally contains no service-bypass policy. It provides generic
version fingerprinting, patch orchestration, diagnostics and transactional writes.
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

__all__ = [
    "BuildProfile",
    "DoctorReport",
    "FileTransaction",
    "Fingerprint",
    "InventoryItem",
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
    "TransactionError",
    "apply_patch",
    "inspect_installation",
    "inspect_marker_feature",
    "inspect_marker_installation",
    "inspect_patch",
    "inventory",
    "match_profile",
    "sha256_file",
]
