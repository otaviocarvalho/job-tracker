# STATE.md - Project Memory

## Decisions

### AD-0001: Vertical feed slices + decorator registry (active, 2026-09-05)

Feeds are self-contained vertical slices in `src/jobtracker/feeds/` (one module per source type, owning fetch + parse + `@register`). `registry.py` maps `sources.yaml:type` to scrape functions and never imports feeds; `feeds/__init__.py` auto-discovers modules via `pkgutil`. Adding a feed = one new module + one `sources.yaml` entry, no dispatcher edits. Dependency rule: `feeds → core` allowed; `core` must never import `feeds`/`registry`/`pipeline` (enforced by import-lint test).

### AD-0002: Cron stdout contract is frozen (active, 2026-09-05)

Hermes cron `e61ce479c5ee` runs `cd ~/code/job-tracker && /usr/bin/python3 main.py 2>/dev/null` and greps stdout for the DIGEST section. `main.py` stays at the repo root, flags stay `--reset/--source/--dry-run`, stdout text stays byte-compatible (golden test on `--source ramp --dry-run`). Runtime deps stay stdlib + PyYAML (present for system python). Do not switch the cron to `poetry run` without a new decision.

### AD-0003: Poetry manages dev environment (active, 2026-09-05)

`pyproject.toml` (poetry) declares PyYAML as the only runtime dep, pytest in the dev group; `poetry.lock` is committed. Poetry installs the root package editable, so tests import `jobtracker` directly; the cron path needs no install thanks to the `main.py` src bootstrap.

### AD-0004: Test isolation via JOBTRACKER_DATA_DIR (active, 2026-09-05)

`core/seen.py` resolves its data directory from `JOBTRACKER_DATA_DIR` when set (default `<repo>/data/`). All store/pipeline tests set it to a tmp dir. Tests must never read or write the production `data/seen.db`.

## Handoff Snapshot

- **Feature**: vertical-slicing - ALL 8 TASKS COMPLETE (T1-T8), 76 tests passing, golden stdout byte-identical, live full-cycle dry run verified (465 raw listings, 33 scored, 6 strong + 27 worth), production seen.db untouched (106 rows before and after)
- **Branch**: `refactor/vertical-slicing` in worktree `~/code/job-tracker-arch`; wiki pointer pushed to obsidian-otavio (299205f)
- **Next step**: Verifier validation, then push branch + ask Otavio about merging to master (cron fires from master)
