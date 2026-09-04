# Changelog

## 1.6.0 - engineering branch

### Added

- Unified `cursor-sand-toolkit` 1.6 command router.
- Thin root launcher plus `python -m cursor_sand_core` entrypoint.
- Frozen 1.5.8 compatibility runtime and narrow forwarding adapter.
- `cursor_sand_core` engineering package.
- Canonical 1.6 version metadata.
- Generic `PatchSpec`/`PatchState` orchestration primitives.
- Build fingerprint and profile matching primitives.
- Transactional multi-file staging with rollback.
- Read-only marker diagnostics for existing installations.
- Bundle inventory with SHA-256 fingerprints.
- `doctor` and `inventory` subcommands with JSON output.
- Cross-platform Pytest matrix and dedicated Ruff/compile/CLI smoke job.
- Release regression-test gate, packaged-binary smoke test and `SHA256SUMS.txt` generation.

### Changed

- `cursor-sand-toolkit.py` is now a thin 1.6 launcher instead of the historical monolith.
- Package distribution is now named `cursor-sand-toolkit` at version `1.6.0`.
- PyInstaller explicitly collects the modular package and verifies the resulting binary starts successfully.

### Compatibility

- Existing 1.5.8 command behavior is retained through `cursor_sand_core.compat`.
- The former root runtime is stored unchanged as `cursor_sand_core/legacy_runtime.py`.
- The frozen runtime is compiled and packaged but excluded from 1.6 Ruff reformatting.
