# Changelog

## 1.6.0 - engineering branch

### Added

- `cursor_sand_core` engineering package.
- Generic `PatchSpec`/`PatchState` orchestration primitives.
- Build fingerprint and profile matching primitives.
- Transactional multi-file staging with rollback.
- Read-only marker diagnostics for existing installations.
- Bundle inventory with SHA-256 fingerprints.
- `cursor-sand-doctor` text and JSON CLI.
- Cross-platform Pytest matrix and dedicated Ruff/compile smoke job.
- Release regression-test gate and `SHA256SUMS.txt` generation.

### Compatibility

- Existing `cursor-sand-toolkit.py` runtime behavior is intentionally unchanged in this branch.
- Feature-specific modification logic remains in the legacy script until it has fixture-backed regression coverage.
