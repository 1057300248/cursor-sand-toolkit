# Contributing

## Development setup

```bash
python -m pip install -e .[dev]
python -m ruff check cursor_sand_core tests
python -m pytest
```

## Patch migration contract

Do not migrate a feature-specific modification into the engineering core without a regression fixture or synthetic equivalent that proves:

1. the original state is detected exactly once;
2. apply produces the expected patched state;
3. a second apply is idempotent;
4. restore returns the original bytes/content;
5. ambiguous input is rejected without modification;
6. missing anchors are reported explicitly;
7. multi-file writes roll back on failure.

## Version compatibility

Prefer build fingerprints and explicit profile matches over a single application version string. A profile should identify the exact target files it recognizes and should fail closed when fingerprints do not match.

## Diagnostics

Diagnostic code must remain read-only. `cursor-sand-doctor` may inspect files, count known markers and calculate hashes, but it must not modify an installation.

## Pull requests

Keep refactors separate from feature changes where possible. Include tests for new core behavior and describe any compatibility assumptions in the PR body.
