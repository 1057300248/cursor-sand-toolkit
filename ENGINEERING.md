# Engineering v1.6

This branch introduces a maintainability layer without changing the existing `main` runtime path.

## Goals

- Separate patch orchestration from feature-specific patch definitions.
- Detect builds by file fingerprints instead of relying on a single version string.
- Make file updates transactional and recoverable.
- Add a structured doctor/reporting layer.
- Require tests before future patch modules are migrated.

## Current modules

- `cursor_sand_core/patching.py`: generic `PatchSpec` model, state inspection, apply/restore flow.
- `cursor_sand_core/profiles.py`: SHA-256 build fingerprints and profile matching.
- `cursor_sand_core/transaction.py`: atomic multi-file staging with rollback on commit failure.
- `cursor_sand_core/doctor.py`: structured health report with JSON output support.

## Migration rule

Existing behavior in `cursor-sand-toolkit.py` remains untouched during the first phase. Feature patches should be migrated one module at a time only after a fixture test exists for that feature.

Recommended order:

1. performance / TTFT diagnostics
2. rules and skills state detection
3. MCP diagnostics
4. Agent Window state detection
5. task/sub-agent state detection

## Required regression contract

Every migrated patch should have tests for:

1. original -> patched
2. second apply is idempotent
3. patched -> original restore
4. ambiguous input is not modified
5. missing anchor is reported instead of silently modified

## CI

`.github/workflows/quality.yml` runs Ruff and Pytest on Python 3.10/3.12 across Linux, Windows and macOS.
