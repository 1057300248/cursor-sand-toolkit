# Contributing

## Development setup

```bash
python -m pip install -e .[dev]
python -m ruff check cursor_sand_core tests
python -m pytest
cursor-sand-toolkit --version
```

## Architecture rule

`cursor-sand-toolkit.py` is a thin launcher. New behavior belongs in focused modules under `cursor_sand_core/`.

`cursor_sand_core/legacy_runtime.py` is the frozen 1.5.8 compatibility executor. Do not opportunistically format, rename, optimize or mix unrelated changes into that file. Existing commands reach it only through `cursor_sand_core.compat`.

## Patch migration contract

Do not migrate a feature-specific modification into a new module without a regression fixture or synthetic equivalent that proves:

1. the original state is detected exactly once;
2. apply produces the expected patched state;
3. a second apply is idempotent;
4. restore returns the original bytes/content;
5. ambiguous input is rejected without modification;
6. missing anchors are reported explicitly;
7. multi-file writes roll back on failure.

Migrations should be one feature at a time so compatibility failures can be attributed to a single module.

## Version compatibility

Prefer build fingerprints and explicit profile matches over a single application version string. A profile should identify the exact target files it recognizes and should fail closed when fingerprints do not match.

## Diagnostics

Diagnostic code must remain read-only. `cursor-sand-toolkit doctor` and `cursor-sand-doctor` may inspect files, count known markers and calculate hashes, but they must not modify an installation.

## CI expectations

Changes must keep the following green:

- Ruff for new 1.6 modules;
- compile checks including the compatibility runtime;
- unified CLI smoke tests;
- Pytest on Python 3.10/3.12 across Linux, Windows and macOS;
- the PyInstaller package smoke job.

## Pull requests

Keep refactors separate from feature changes where possible. Include tests for new core behavior and describe compatibility assumptions in the PR body.
