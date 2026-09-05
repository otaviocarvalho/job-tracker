# STATE.md - Project Memory

## Decisions

### AD-0001: Vertical feed slices + decorator registry (active, 2026-09-05)

Feeds are self-contained vertical slices in `src/jobtracker/feeds/` (one module per source type, owning fetch + parse + `@register`). `registry.py` maps `sources.yaml:type` to scrape functions and never imports feeds; `feeds/__init__.py` auto-discovers modules via `pkgutil`. Adding a feed = one new module + one `sources.yaml` entry, no dispatcher edits. Dependency rule: `feeds → core` allowed; `core` must never import `feeds`/`registry`/`pipeline` (enforced by import-lint test).

### AD-0002: Cron stdout contract is frozen (interpreter clause superseded by AD-0005, 2026-09-05)

The stdout rules of this decision remain in force: Hermes cron `e61ce479c5ee` greps stdout for the DIGEST section; `main.py` stays at the repo root, flags stay `--reset/--source/--dry-run`, stdout text stays byte-compatible (golden test on `--source ramp --dry-run`). Only the interpreter clause changed (see AD-0005).

### AD-0003: Poetry manages dev environment (active, 2026-09-05)

`pyproject.toml` (poetry) declares PyYAML as the only runtime dep, pytest in the dev group; `poetry.lock` is committed. Poetry installs the root package editable, so tests import `jobtracker` directly; the cron path needs no install thanks to the `main.py` src bootstrap.

### AD-0004: Test isolation via JOBTRACKER_DATA_DIR (active, 2026-09-05)

`core/seen.py` resolves its data directory from `JOBTRACKER_DATA_DIR` when set (default `<repo>/data/`). All store/pipeline tests set it to a tmp dir. Tests must never read or write the production `data/seen.db`.

### AD-0005: Cron runs the repo's in-project poetry venv (active, 2026-09-05)

Supersedes the interpreter clause of AD-0002 (Otavio's call, 2026-09-05: the cron is not critical and may fail until fixed if the venv breaks). The cron executes `cd ~/code/job-tracker && .venv/bin/python main.py 2>/dev/null`. `poetry.toml` (committed) pins `virtualenvs.in-project = true`; `poetry install` creates/syncs `.venv` with PyYAML locked by `poetry.lock`. The stdout contract (frozen wording, golden tests, DIGEST grep) is unchanged. System python (with PyYAML) remains a working fallback path. Never point the cron at bare `poetry run` (env resolution is shell-dependent on this box); call `.venv/bin/python` directly.

## Handoff Snapshot

- **Feature**: vertical-slicing delivered, verified, and merged to master (b8af9a9); AGENTS.md added (657ce49); cron migrated to the in-project venv per AD-0005 (dc293a4+)
- **Cron**: job `e61ce479c5ee` now runs `cd ~/code/job-tracker && .venv/bin/python main.py 2>/dev/null`; `.venv` (Python 3.11) created via `poetry install`; golden byte-match and 76 tests green under `.venv/bin/python`
- **Next step**: none pending; if the cron ever fails with a missing interpreter, run `poetry install` in the repo root
