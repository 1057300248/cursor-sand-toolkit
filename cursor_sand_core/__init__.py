"""Reusable engineering primitives for Cursor Sand Toolkit.

This package intentionally contains no service-bypass policy. It provides generic
version fingerprinting, patch orchestration, diagnostics and transactional writes.
"""

from .doctor import DoctorReport, inspect_installation
from .patching import PatchResult, PatchSpec, PatchState, apply_patch, inspect_patch
from .profiles import BuildProfile, Fingerprint, ProfileMatch, match_profile
from .transaction import FileTransaction, TransactionError

__all__ = [
    "BuildProfile",
    "DoctorReport",
    "FileTransaction",
    "Fingerprint",
    "PatchResult",
    "PatchSpec",
    "PatchState",
    "ProfileMatch",
    "TransactionError",
    "apply_patch",
    "inspect_installation",
    "inspect_patch",
    "match_profile",
]
