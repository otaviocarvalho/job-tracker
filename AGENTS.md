# AGENTS.md

Guidance for AI agents working in this codebase. Read this before making changes.

- **Architecture**: [ARCH.md](ARCH.md) is the doc of record (vertical feed slices, registry, feed contract, dependency rule, cron stdout contract, testing policy).
- **Operations**: [README.md](README.md) has the feeds table and the Hermes cron setup.
- **Decisions and specs**: `.specs/STATE.md` (decision log AD-0001..AD-0004), `.specs/features/` (spec-driven features with validation reports).

## What this is

A standalone CLI that scrapes job feeds, scores listings against the profile in `config/criteria.yaml`, dedups via SQLite, and prints a markdown digest to stdout. A Hermes cron (every 6h) runs `cd ~/code/job-tracker && .venv/bin/python main.py 2>/dev/null` and relays the digest to Telegram. Code and scheduling are decoupled: stdout is the only contract with the cron.

## Setup

```bash
poetry install                 # creates/syncs .venv (if another venv is active in the shell: env -u VIRTUAL_ENV poetry install)
.venv/bin/python -m pytest     # must be green before and after any change
```

Each checkout binds its own venv: run `poetry install` once per clone/worktree (`poetry.toml` pins the env to `.venv` inside the project). Invoke the interpreter and pytest directly via `.venv/bin/python`: on this machine a shell may have another venv active, and `poetry run` would bind to it instead of the project's `.venv`.

## Non-negotiable contracts

1. **Entrypoint**: `main.py` stays at the repo root and bootstraps `src/` onto `sys.path` itself. The cron runs `.venv/bin/python main.py` (poetry in-project venv; recreate with `poetry install` if missing). Runtime dependencies: stdlib + PyYAML only. System python (with PyYAML) remains a working fallback.
2. **Stdout is frozen**: the cron greps output for the digest section. Do not reword, reformat, or add output. If a change to output wording is truly required, regenerate the golden constants in `tests/test_cli.py` and update the cron prompt in README.md in the same change.
3. **Dedup state is precious**: a real run marks listings seen irreversibly. Test with `--dry-run` first. Never read or write `data/seen.db` from tests or throwaway runs; set `JOBTRACKER_DATA_DIR` to a temp dir instead.
4. **Dependency rule**: `core/` never imports `feeds/`, `registry`, `pipeline`, or `cli` (enforced by `tests/core/test_imports.py`). `registry` never imports `feeds` (registration flows through the decorator). `feeds/` may use `core` and `registry`.
5. **Feeds never raise**: on any error, print `  [<feed>:<id>] Error: ...` and return `[]`. One dead feed must not kill the digest.

## Adding a feed (the common task)

One new module in `src/jobtracker/feeds/` with a `@register("<type>") scrape(source: dict) -> list[dict]` function, plus one entry in `config/sources.yaml`. Nothing else changes; the package auto-discovers modules. Full steps and the listing contract: ARCH.md, section "How to add a new feed". Add network-free unit tests for the new slice (mock `urllib.request.urlopen`; see `tests/feeds/conftest.py`).

## Change discipline

- Features go through the spec-driven flow in `.specs/features/`: spec with testable acceptance criteria, atomic tasks, tests per task, independent verification. Do not land unverified refactors of the pipeline or scoring.
- Conventional Commits (`feat`, `fix`, `refactor`, `docs`, `test`, `chore`), one logical change per commit, tests in the same commit as the code they cover.
- Run `.venv/bin/python -m pytest` before every commit; capture the exit code explicitly, never pipe pytest through `tail` for the verdict.
- The cron invokes `.venv/bin/python` directly (AD-0005 supersedes AD-0002's interpreter clause). After changing dependencies, run `poetry install` so `.venv` is synced, and never point the cron at `poetry run` or a bare interpreter without a new decision in `.specs/STATE.md`.
- On the deployment machine, develop risky changes in a git worktree on a branch (the main checkout feeds the live cron) and `git pull --rebase` before starting; the repo is `github.com/otaviocarvalho/job-tracker` (private, default branch `master`).

## Known sharp edges

- HN "Who's Hiring" comments produce run-on junk titles; titles are truncated to 120 chars but stay noisy. Cosmetic, do not "fix" casually: scoring depends on the text shape.
- YC enrichment fetches detail pages for keyword-matching titles only (cap 12, 0.5s sleep). Keep the politeness caps.
- infra.nyc is a Next.js RSC payload and YC is an Inertia payload: parse the embedded data, never the rendered shell. Empty results usually mean an anti-bot response (406/shell HTML), not "no jobs".
