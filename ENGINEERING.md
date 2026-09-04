# Engineering v1.6

Version 1.6 moves the executable entrypoint and engineering services into a package while preserving the 1.5.8 executor as an unchanged compatibility runtime.

## Runtime layout

```text
cursor-sand-toolkit.py
        |
        v
cursor_sand_core.cli
   |-- version / doctor / inventory   -> v1.6 modules
   `-- existing commands              -> compat.run_legacy()
                                             |
                                             v
                                  legacy_runtime.py (frozen 1.5.8)
```

The root script is now only a thin launcher. New engineering work no longer needs to grow the historical single-file entrypoint.

## Modules

- `cursor_sand_core/cli.py`: unified 1.6 command router.
- `cursor_sand_core/compat.py`: narrow adapter into the frozen 1.5.8 executor.
- `cursor_sand_core/legacy_runtime.py`: byte-equivalent copy of the former 1.5.8 root runtime.
- `cursor_sand_core/version.py`: canonical package/version metadata.
- `cursor_sand_core/patching.py`: generic `PatchSpec` model, state inspection and apply/restore flow.
- `cursor_sand_core/profiles.py`: SHA-256 build fingerprints and profile matching.
- `cursor_sand_core/transaction.py`: atomic multi-file staging with rollback on commit failure.
- `cursor_sand_core/doctor.py`: generic patch-health reporting.
- `cursor_sand_core/marker_doctor.py`: read-only marker diagnostics for existing installations.
- `cursor_sand_core/catalog.py`: known diagnostic features and target files.
- `cursor_sand_core/inventory.py`: target-file size and SHA-256 inventory.
- `cursor_sand_core/doctor_cli.py`: text/JSON diagnostics command.
- `cursor_sand_core/inventory_cli.py`: bundle fingerprint command.

## Unified CLI

Install the package for development:

```bash
python -m pip install -e .
```

Version information:

```bash
cursor-sand-toolkit --version
python -m cursor_sand_core --version
```

Read-only diagnostics:

```bash
cursor-sand-toolkit doctor /path/to/Cursor/resources/app
cursor-sand-toolkit doctor /path/to/Cursor/resources/app --json
cursor-sand-toolkit doctor /path/to/Cursor/resources/app --strict
```

Bundle fingerprints:

```bash
cursor-sand-toolkit inventory /path/to/Cursor/resources/app
cursor-sand-toolkit inventory /path/to/Cursor/resources/app --json
```

Existing 1.5.8 commands are forwarded without rewriting their implementation.

## Compatibility contract

The compatibility runtime is deliberately frozen. New 1.6 code may change routing, diagnostics, packaging, build detection, testing and transaction infrastructure, but the historical executor is not auto-formatted or behaviorally rewritten as part of this migration.

This gives the branch a stable transition path:

1. the executable and package architecture are already 1.6;
2. existing commands keep their prior implementation;
3. future feature migrations can be performed one at a time behind regression tests;
4. the root script never needs to become a monolith again.

## Required regression contract

Every newly migrated patch module should have tests for:

1. original -> patched
2. second apply is idempotent
3. patched -> original restore
4. ambiguous input is not modified
5. missing anchor is reported instead of silently modified
6. transaction rollback preserves original bytes on failure

The compatibility router itself is tested to ensure old command arguments are passed through unchanged.

## CI and release

`.github/workflows/quality.yml` provides:

- Ruff for new 1.6 modules (the frozen legacy runtime is excluded from reformatting);
- compile checks including the compatibility runtime;
- unified CLI and module-entrypoint smoke tests;
- Pytest on Python 3.10 and 3.12 across Linux, Windows and macOS.

`.github/workflows/build.yml` additionally:

- runs the regression suite before packaging;
- explicitly collects all `cursor_sand_core` submodules in PyInstaller;
- smoke-tests the packaged executable with `--version`;
- publishes SHA-256 checksums for release archives.

## Safety boundary

The 1.6 engineering work improves structure, diagnostics, testing, fingerprinting, packaging and transactional file handling. It does not add or strengthen service-limit, billing or abuse-control bypass behavior.
