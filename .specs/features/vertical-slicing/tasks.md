# Vertical Slicing Architecture Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/vertical-slicing/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: none - strong defaults applied (no AGENTS.md/CONTRIBUTING/CI config in repo; repo currently has zero tests).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| core/scoring (domain) | unit | All branches; 1:1 to spec ACs (hard reject, require-any, title/tech/domain keywords, remote/EU bonus, 100 cap, tiers) | `tests/core/test_scoring.py` | `poetry run pytest -q` |
| core/seen (data-access) | unit | Key paths (mark, is_seen, filter_unseen, mark_all_seen, clear_all) + isolation via JOBTRACKER_DATA_DIR | `tests/core/test_seen.py` | `poetry run pytest -q` |
| core/digest (domain) | unit | Empty input, strong/worth grouping, ordering, signal truncation to 5 | `tests/core/test_digest.py` | `poetry run pytest -q` |
| core/config (config) | unit | Loaders return YAML shapes; repo_root resolution | `tests/core/test_config.py` | `poetry run pytest -q` |
| registry (extension point) | unit | register/get/registered_types, dispatch passes full source entry, unknown-type message, zero-touch discovery | `tests/test_registry.py` | `poetry run pytest -q` |
| feeds (parsing) | unit | Each feed's parse/extract logic network-free (mocked urllib or pure functions); error convention; standardized dict shape | `tests/feeds/test_<feed>.py` | `poetry run pytest -q` |
| pipeline + cli (orchestration/contract) | unit + golden | Scrape→score→dedup→digest→mark-seen order, --dry-run skips mark, --reset clears, no-match path, golden stdout byte-match of `main.py --source ramp --dry-run` | `tests/test_pipeline.py`, `tests/test_cli.py` | `poetry run pytest -q` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. NOTE: run pytest bare or capture the exit code explicitly (`poetry run pytest -q >/dev/null 2>&1; echo exit=$?`) - never pipe through tail.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After every task | `cd ~/code/job-tracker-arch && poetry run pytest -q` |
| Full | After pipeline/CLI cutover and docs tasks | `poetry run pytest -q` + `/usr/bin/python3 main.py --source ramp --dry-run` byte-matches `/tmp/jt_baseline_report.txt` |
| Build | After final task | Full gate + `git -C ~/code/job-tracker-arch status --porcelain` shows a clean tree |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Foundation

```
T1
```

### Phase 2: Core Kernel

```
T2
T3
```

### Phase 3: Registry + Feeds

```
T4
T5
```

### Phase 4: Pipeline Cutover

```
T6
```

### Phase 5: Documentation + Live Verification

```
T7
T8
```

---

## Task Breakdown

### T1: Poetry packaging scaffold

**What**: Add `pyproject.toml` (poetry; pyyaml `^6.0` runtime; pytest `^8.0` dev group; `packages = [{include = "jobtracker", from = "src"}]`; pytest testpaths), `src/jobtracker/__init__.py` skeleton, updated `.gitignore` (`.venv/`, `__pycache__/`, `.pytest_cache/`, `data/`, `dist/`); run `poetry lock && poetry install` and commit `poetry.lock`.
**Where**: `pyproject.toml`, `poetry.lock`, `.gitignore`, `src/jobtracker/__init__.py`
**Depends on**: None
**Reuses**: dependency facts from `README.md` (Python 3.11+, PyYAML)
**Requirement**: ARCH-01, ARCH-02, ARCH-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `poetry install` succeeds and `poetry run python -c "import jobtracker, yaml, pytest"` exits 0
- [x] `poetry run pytest -q` runs (0 tests collected is acceptable at this task; exit 0)
- [x] `/usr/bin/python3 -c "import sys; sys.path.insert(0,'src'); import jobtracker"` exits 0 (cron-path bootstrap works without install)

**Tests**: unit
**Gate**: quick

**Commit**: `build: poetry packaging with pytest dev group and lockfile`

---

### T2: Extract core config + scoring kernel

**What**: Create `src/jobtracker/core/` with `config.py` (`repo_root()`, `load_sources()`, `load_criteria()` merging old `filters/criteria.py`) and `scoring.py` (verbatim move of `filters/matcher.py`, criteria loaded via `core.config`). Add import-lint test asserting no `core` module imports `feeds`/`registry`/`pipeline`/`cli`, plus full scoring unit tests against `config/criteria.yaml` values.
**Where**: `src/jobtracker/core/config.py`, `src/jobtracker/core/scoring.py`, `src/jobtracker/core/__init__.py`, `tests/core/test_scoring.py`, `tests/core/test_config.py`, `tests/core/test_imports.py`
**Depends on**: T1
**Reuses**: `src/filters/matcher.py` (verbatim body), `src/filters/criteria.py` (loader)
**Requirement**: ARCH-10, ARCH-12, ARCH-17

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Scoring tests pass: reject keywords, require-any fallback, positive title/tech/domain scoring with criteria.yaml points, remote +10 / EU +8 exclusivity, cap at 100, tier thresholds 70/45
- [x] Import-lint test passes (AST-walk of `core/*.py`)
- [x] Gate check passes: `poetry run pytest -q` green; test count reported (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `refactor(core): extract config loaders and profile scoring kernel`

---

### T3: Extract dedup store + digest with test isolation

**What**: Move `store/seen.py` → `core/seen.py` (verbatim API; `_db_path()` resolves `JOBTRACKER_DATA_DIR` env at call time, default `<repo_root>/data/seen.db`) and `output/digest.py` → `core/digest.py` (verbatim). Unit tests for the store (temp dir via monkeypatch env) and digest formatter.
**Where**: `src/jobtracker/core/seen.py`, `src/jobtracker/core/digest.py`, `tests/core/test_seen.py`, `tests/core/test_digest.py`
**Depends on**: T2
**Reuses**: `src/store/seen.py`, `src/output/digest.py`, `core/config.repo_root()`
**Requirement**: ARCH-11, ARCH-18, ARCH-19

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Store tests pass against isolated temp DB: empty-url listing tracked, INSERT OR IGNORE idempotence, filter_unseen, clear_all; assert the resolved path is inside tmp dir (never repo `data/`)
- [x] Digest tests pass: empty → "", grouping strong-then-worth, signals capped at 5
- [x] Gate check passes: `poetry run pytest -q` green

**Tests**: unit
**Gate**: quick

**Commit**: `refactor(core): extract dedup store and digest with env-based test isolation`

---

### T4: Feed registry with decorator + dispatch

**What**: Create `src/jobtracker/registry.py`: `register(feed_type)` decorator, `_REGISTRY` map, `get()`, `registered_types()`, `scrape_source(source)` dispatching with the full source entry and printing `  Unknown source type: <type>` for unregistered types. Unit tests (decorator stores, dispatch passes name/type/url/config through, unknown type message + empty result). No feed modules yet.
**Where**: `src/jobtracker/registry.py`, `tests/test_registry.py`
**Depends on**: T2
**Reuses**: semantics of `main.py::scrape_source` elif chain
**Requirement**: ARCH-06, ARCH-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Registry tests pass: registration, lookup, dispatch contract (feed receives the whole source dict), unknown-type behavior matches legacy output
- [x] `registry.py` imports nothing from `feeds` (covered by import-lint test)
- [x] Gate check passes: `poetry run pytest -q` green

**Tests**: unit
**Gate**: quick

**Commit**: `refactor(registry): type-to-feed registry with decorator registration`

---

### T5: Vertical feed slices with auto-discovery

**What**: Create `src/jobtracker/feeds/` package: `__init__.py` auto-imports every module via `pkgutil.iter_modules(__path__)`; move all 7 scrapers as self-contained slices (`greenhouse.py`, `hackernews.py`, `infranyc.py`, `report.py`, `speedrun.py`, `substack.py`, `ycombinator.py`), each defining `@register("<type>") scrape(source: dict) -> list[dict]` adapting its legacy signature; ycombinator enrichment keywords switch to `core.config.load_criteria()`. Unit tests per feed (parse/extract logic network-free via mocked `urllib` responses or pure-function calls) + zero-touch discovery test (temp module written into the feeds dir registers on package reload, cleaned up after).
**Where**: `src/jobtracker/feeds/` (8 files), `tests/feeds/test_<feed>.py` (7 files), `tests/feeds/test_discovery.py`
**Depends on**: T4
**Reuses**: `src/scrapers/*.py` bodies (near-verbatim, signature adaptation only)
**Requirement**: ARCH-04, ARCH-05, ARCH-08, ARCH-09, ARCH-13

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] All 7 feed types registered after `import jobtracker.feeds`; `registered_types()` == greenhouse, hackernews, infranyc, report, speedrun, substack, ycombinator
- [ ] Zero-touch test: a new module file with `@register` becomes discoverable without editing any other file
- [ ] Per-feed tests pass network-free: greenhouse JSON→listings + location fallback; hackernews comment parse (pipe format, title detection, reply skip, short-comment skip) with mocked thread discovery; ycombinator Inertia payload extraction + enrichment keyword gating; substack RSS item extraction (publication and url variants); speedrun synthetic description assembly; infranyc RSC chunk reassembly + `_extract_json_array` bracket matching; report manual-review notice
- [ ] Error convention asserted for at least greenhouse + speedrun: exception → printed `  [<feed>:<id>] Error: ...` + `[]`
- [ ] Gate check passes: `poetry run pytest -q` green

**Tests**: unit
**Gate**: quick

**Commit**: `refactor(feeds): vertical feed slices with auto-discovered registry`

---

### T6: Pipeline + CLI cutover, remove legacy layers

**What**: Create `pipeline.py` (verbatim `run()` from `main.py`; sources via `core.config.load_sources`, dispatch via `registry.scrape_source`, scoring/seen/digest via core) and `cli.py` (verbatim argparse block, `main()`); rewrite `main.py` as thin shim (docstring + `sys.path` src bootstrap + `cli.main()`); DELETE `src/scrapers/`, `src/filters/`, `src/store/`, `src/output/`. Unit tests: pipeline orchestration with monkeypatched dispatch (order scrape→score→dedup→digest→mark-seen; `--dry-run` skips mark; `--reset` clears; source name filter; empty-listings early return), CLI flag parsing, and the golden stdout byte-match test running `main.py --source ramp --dry-run` via subprocess.
**Where**: `src/jobtracker/pipeline.py`, `src/jobtracker/cli.py`, `main.py`, deletion of legacy layer dirs, `tests/test_pipeline.py`, `tests/test_cli.py`
**Depends on**: T5
**Reuses**: `main.py` run()/argparse bodies (verbatim), golden baseline `/tmp/jt_baseline_report.txt`
**Requirement**: ARCH-03, ARCH-06, ARCH-13, ARCH-14, ARCH-15, ARCH-16, ARCH-20, ARCH-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Golden stdout test passes: subprocess `[sys.executable, "main.py", "--source", "ramp", "--dry-run"]` byte-matches the embedded baseline captured pre-refactor
- [ ] Pipeline tests pass: orchestration order, dry-run skips mark_seen, reset clears store, filter by source name, zero-sources and zero-listings early returns
- [ ] Legacy dirs gone; `grep -r "src/scrapers\|src/filters\|src/store\|src/output" src/ main.py` returns nothing
- [ ] Gate check passes: full gate - `poetry run pytest -q` green AND `/usr/bin/python3 main.py --source ramp --dry-run` in the worktree byte-matches baseline

**Tests**: unit
**Gate**: full

**Commit**: `refactor(pipeline): orchestrate via registry, freeze CLI contract, drop legacy layers`

---

### T7: ARCH.md + README architecture pointer

**What**: Write `ARCH.md` as the architecture doc of record: vertical-slice structure diagram, dependency rule (feeds→core), feed contract (`scrape(source)` + standardized dict + error convention), step-by-step "add a new feed", cron stdout contract, config roles, testing policy (JOBTRACKER_DATA_DIR isolation, network-free suite). Update `README.md`: Architecture section now points to `ARCH.md` (wiki pointer removed), Dependencies section updated to poetry workflow, Quick Start gains poetry commands.
**Where**: `ARCH.md`, `README.md`
**Depends on**: T6
**Reuses**: design.md content, wiki page content, spec contract sections
**Requirement**: ARCH-23, ARCH-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `ARCH.md` covers all six required topics (structure, dependency rule, feed contract, add-a-feed steps, cron contract, config roles)
- [ ] `README.md` no longer references the Obsidian wiki path; links `ARCH.md`
- [ ] Gate check passes: `poetry run pytest -q` green (docs change breaks nothing)

**Tests**: none
**Gate**: full

**Commit**: `docs: ARCH.md as architecture doc of record; README points to it`

---

### T8: Wiki pointer swap + live full-cycle verification

**What**: In `~/code/obsidian-otavio`, edit `wiki/projects/Job Tracker/Job Tracker.md` Architecture section: add a pointer that the architecture doc of record is now `ARCH.md` in the `otaviocarvalho/job-tracker` repo (wiki section kept as historical profile/source curation). Commit + push that repo. Then run the live read-only verification in the worktree: full cycle `/usr/bin/python3 main.py --dry-run` (all feeds, network, no mark-seen) and confirm per-source raw listing counts are sane vs the pre-refactor behavior.
**Where**: `~/code/obsidian-otavio/wiki/projects/Job Tracker/Job Tracker.md` (separate repo); verification run in `~/code/job-tracker-arch`
**Depends on**: T7
**Reuses**: existing wiki page structure
**Requirement**: ARCH-25

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Wiki page diff shows the ARCH.md pointer (git pull --rebase first; commit + push)
- [ ] Live `--dry-run` full cycle completes: per-source "Got N raw listings" lines present, no tracebacks, digest section formatted, zero listings marked seen (worktree data dir untouched: `data/seen.db` not created in worktree)
- [ ] Build gate: `poetry run pytest -q` green; worktree git tree clean of unexpected files

**Tests**: none
**Gate**: build

**Commit**: `docs: point Job Tracker architecture at repo ARCH.md` (obsidian-otavio repo)

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5

Phase 1:  T1
Phase 2:  T1 → T2 → T3
Phase 3:  T2 → T4 → T5
Phase 4:  T5 → T6
Phase 5:  T6 → T7 → T8
```

---

## Task Granularity Check

| Task | Scope | Status |
| ------------------------------- | ------------- | ------------ |
| T1: Poetry scaffold | 1 packaging unit | ✅ Granular |
| T2: core config + scoring | 2 cohesive files, 1 kernel concept | ✅ Granular |
| T3: core seen + digest | 2 cohesive files, 1 kernel concept | ✅ Granular |
| T4: registry module | 1 module | ✅ Granular |
| T5: feeds package (7 slices) | 1 package, 1 concept (slices + discovery) | ✅ Granular (cohesive move) |
| T6: pipeline + cli + shim + deletions | 1 cutover concept | ✅ Granular |
| T7: ARCH.md + README | docs pair, 1 concept | ✅ Granular |
| T8: wiki pointer + live verify | 1 docs edit + 1 verification | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | (no incoming) | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T2 | T2 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1 | packaging/config | none (build gate only) | unit (smoke) | ✅ OK |
| T2 | core/scoring + core/config (domain) | unit | unit | ✅ OK |
| T3 | core/seen (data) + core/digest (domain) | unit | unit | ✅ OK |
| T4 | registry (extension point) | unit | unit | ✅ OK |
| T5 | feeds (parsing) | unit | unit | ✅ OK |
| T6 | pipeline + cli (orchestration/contract) | unit + golden | unit | ✅ OK (golden included) |
| T7 | docs | none | none | ✅ OK |
| T8 | docs (other repo) + ops verification | none | none | ✅ OK |
