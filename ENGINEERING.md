# Engineering v1.6

This branch introduces a maintainability layer without changing the existing `main` runtime path.

## Goals

- Separate patch orchestration from feature-specific patch definitions.
- Detect builds by file fingerprints instead of relying on a single version string.
- Make file updates transactional and recoverable.
- Add structured, read-only diagnostics with machine-readable output.
- Require regression tests before future patch modules are migrated.

## Current modules

- `cursor_sand_core/patching.py`: generic `PatchSpec` model, state inspection, apply/restore flow.
- `cursor_sand_core/profiles.py`: SHA-256 build fingerprints and profile matching.
- `cursor_sand_core/transaction.py`: atomic multi-file staging with rollback on commit failure.
- `cursor_sand_core/doctor.py`: generic `PatchSpec` health reporting.
- `cursor_sand_core/marker_doctor.py`: read-only marker diagnostics for existing installations.
- `cursor_sand_core/catalog.py`: known diagnostic features and their target files.
- `cursor_sand_core/inventory.py`: target-file size and SHA-256 inventory.
- `cursor_sand_core/doctor_cli.py`: text/JSON command-line diagnostics.

## Doctor

Install the development package:

```bash
python -m pip install -e .
```

Inspect a Cursor `resources/app` directory:

```bash
cursor-sand-doctor /path/to/Cursor/resources/app
```

Machine-readable output:

```bash
cursor-sand-doctor /path/to/Cursor/resources/app --json
```

Strict mode returns exit code `1` if any known diagnostic feature is not healthy:

```bash
cursor-sand-doctor /path/to/Cursor/resources/app --strict
```

The doctor is read-only. It fingerprints known bundles and reports marker state; it never modifies the Cursor installation.

## Migration rule

Existing behavior in `cursor-sand-toolkit.py` remains untouched in this engineering phase. Feature-specific modification logic should be migrated one module at a time only after a fixture/regression test exists for that feature.

## Required regression contract

Every migrated patch should have tests for:

1. original -> patched
2. second apply is idempotent
3. patched -> original restore
4. ambiguous input is not modified
5. missing anchor is reported instead of silently modified
6. transaction rollback preserves original bytes on failure

## CI

`.github/workflows/quality.yml` provides:

- one dedicated Ruff/compile/CLI smoke-test job on Python 3.12;
- Pytest on Python 3.10 and 3.12;
- Linux, Windows and macOS test coverage;
- `fail-fast: false` so all platform failures are visible in one run.

## Safety boundary

The engineering core is intentionally generic. It improves maintainability, diagnostics, testing, fingerprinting and transactional file handling; it does not add or strengthen service-limit, billing or abuse-control bypass behavior.
