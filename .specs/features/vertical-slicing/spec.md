# Vertical Slicing Architecture (Poetry Migration) Specification

## Problem Statement

The job tracker is organized in technical layers (`src/scrapers/`, `src/filters/`, `src/store/`, `src/output/`) with an if/elif dispatcher in `main.py`. Adding a feed requires touching the dispatcher, and there is no packaging, no lockfile, and zero tests. The architecture doc lives outside the repo in the Obsidian wiki, so the repo has no self-contained source of truth. Otavio wants a vertically sliced, extensible structure (add more feeds easily), poetry for dependency management, unit tests, and the architecture documented in a repo-level `ARCH.md`.

## Goals

- [ ] Restructure to vertical feature slices: one self-contained module per feed under `src/jobtracker/feeds/`, with a decorator registry and auto-discovery; adding a feed = adding one module, zero dispatcher edits
- [ ] Poetry packaging (`pyproject.toml`, `poetry.lock`, dev group with pytest); runtime stays Python 3.11+ stdlib + PyYAML only
- [ ] Unit tests for core (scoring, dedup, digest, config) and every feed slice (parsing logic network-free); tests must not touch the production `data/seen.db`
- [ ] `ARCH.md` in the repo becomes the architecture doc of record; README and the Obsidian wiki page point to it
- [ ] CLI stdout contract preserved: `main.py` entrypoint, same flags, byte-compatible output so the Hermes cron (`e61ce479c5ee`, runs `/usr/bin/python3 main.py 2>/dev/null`, greps DIGEST) keeps working unchanged

## Out of Scope

| Feature | Reason |
| ----------- | -------------- |
| Adding new job feeds | Architecture only; feeds are added later using the new mechanism |
| Changing scoring criteria, thresholds, or digest format | Behavior must stay identical |
| Switching the Hermes cron command to `poetry run` | Cron prompt is pinned; runtime works via `/usr/bin/python3` today; separate decision |
| GitHub Actions CI | Not requested; local pytest gate only |
| Feed behavior changes (headers, enrichment caps, retries) | Pure refactor: extract/move, do not improve scrapers |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | --------------- | --------- | ---------- |
| Worktree vs direct on master | Refactor on branch `refactor/vertical-slicing` in `~/code/job-tracker-arch` | Standing rule: cron-driven repos get risky changes in a worktree; cron keeps firing old-but-green master. Push branch; merge on explicit go-ahead | y (standing rule) |
| Feed contract shape | Uniform `scrape(source: dict) -> list[dict]`, `source` = full YAML entry | Current signatures are heterogeneous (`scrape(board, name)`, `scrape(publication, url, name)`); a uniform contract is what makes the registry possible | y |
| Registry mechanism | Decorator `@register("type")` + pkgutil auto-discovery of `src/jobtracker/feeds/*.py` | Zero-touch extensibility: new feed module = new file, no edits elsewhere (open/closed) | y |
| Listing data model | Keep plain dicts (`{title, company, url, location, description, source}`), no dataclass | Minimizes churn; contract is documented in `base.py` and ARCH.md | y |
| Runtime interpreter for cron | Unchanged: `/usr/bin/python3 main.py` (3.12, system user PyYAML) | Cron prompt is pinned; code stays stdlib+PyYAML so the contract holds with zero cron changes | y |
| Poetry install method | pip `--user` (done, Poetry 2.4.3 at `~/.local/bin/poetry`) | Playa has no poetry/pipx; PyPI reachable from host pip | y |
| Wiki update | Edit Obsidian wiki page's Architecture section to point at repo `ARCH.md` | "Use it instead" implies the wiki stops being the architecture doc of record | y |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: Poetry Packaging ⭐ MVP

**User Story**: As a maintainer, I want poetry-managed dependencies with a lockfile so that dev setup and test runs are reproducible.

**Why P1**: Requested explicitly; the test gate depends on it.

**Acceptance Criteria** (each line is one EARS pattern):

1. WHEN `poetry install` runs in the repo root THEN poetry SHALL create an environment containing `pyyaml` (runtime) and `pytest` (dev group) and lock them in `poetry.lock`  <!-- event-driven -->
2. The project SHALL declare PyYAML as its only runtime dependency and Python `>=3.11`  <!-- ubiquitous -->
3. WHEN `/usr/bin/python3 main.py` runs from the repo root THEN the program SHALL execute without any pip-installed project package (src-path bootstrap in the entrypoint)  <!-- event-driven -->

**Independent Test**: `poetry install && poetry run pytest` passes; `/usr/bin/python3 main.py --source ramp --dry-run` produces the golden baseline output.

---

### P2: Vertical Feed Slices with Registry ⭐ MVP

**User Story**: As a maintainer, I want each feed as a self-contained vertical slice so that adding a feed is one new module with no dispatcher edits.

**Why P2**: The core extensibility ask ("add more feeds in the future").

**Acceptance Criteria**:

1. The system SHALL organize feeds as one self-contained module per feed type under `src/jobtracker/feeds/`, each owning its fetch, parse, and `@register` declaration  <!-- ubiquitous -->
2. WHEN a new module containing a `@register`-decorated scrape function is placed in `src/jobtracker/feeds/` THEN the registry SHALL discover it automatically with no edits to any other module  <!-- event-driven -->
3. WHEN `sources.yaml` declares a source whose `type` matches a registered feed THEN the pipeline SHALL call that feed's `scrape(source)` passing the full source entry (name, type, url, config)  <!-- event-driven -->
4. IF a source declares a `type` with no registered feed THEN the system SHALL print `Unknown source type: <type>` and return no listings from that source  <!-- unwanted-behavior -->
5. Each feed SHALL return standardized listing dicts `{title, company, url, location, description, source}` and, on any error, print `  [<feed>:<id>] Error: ...` and return `[]` (never raise)  <!-- ubiquitous -->
6. WHERE a source type is `report` (manual check) THEN the feed SHALL print the manual-review notice and return `[]` (current behavior preserved)  <!-- optional-feature -->

**Independent Test**: Registry unit tests prove discovery + dispatch + unknown-type fallback; a fixture feed module in a temp dir proves zero-touch registration.

---

### P3: Shared Core (Dependency Rule) ⭐ MVP

**User Story**: As a maintainer, I want scoring, dedup, digest, and config in a shared core so that feed slices stay thin and business rules live in one place.

**Why P3**: Vertical slicing requires a clear shared kernel and one-way dependencies.

**Acceptance Criteria**:

1. Modules under `src/jobtracker/core/` (scoring, criteria config, seen store, digest) SHALL NOT import from `src/jobtracker/feeds/` or the pipeline  <!-- ubiquitous -->
2. The seen store SHALL resolve its database directory from the `JOBTRACKER_DATA_DIR` environment variable when set, falling back to `<repo>/data/`  <!-- ubiquitous -->
3. The profile criteria SHALL be loaded from `config/criteria.yaml` via one shared loader, and feeds needing profile keywords (ycombinator enrichment) SHALL use that loader instead of reading YAML themselves  <!-- ubiquitous -->
4. The pipeline SHALL orchestrate scrape → score → dedup → digest → mark-seen, skipping mark-seen when `--dry-run` is set (current order preserved)  <!-- ubiquitous -->

**Independent Test**: An import-lint unit test asserts `core` never imports `feeds`/`pipeline`; scoring/dedup/digest unit tests assert behavior; `--dry-run` path asserted by tests and golden output.

---

### P4: CLI Contract Parity

**User Story**: As the Hermes cron, I want `main.py` to behave exactly as before so that the digest delivery pipeline needs no changes.

**Why P4**: The cron greps stdout; silent breakage would kill the digest.

**Acceptance Criteria**:

1. `main.py` SHALL remain the entrypoint at the repo root with identical argparse flags `--reset`, `--source`, `--dry-run`  <!-- ubiquitous -->
2. WHEN run with `--source ramp --dry-run` THEN stdout SHALL byte-match the captured golden baseline (report-type run: header, manual-review notice, zero listings)  <!-- event-driven -->
3. WHEN run with a `--source` filter matching no sources THEN the program SHALL print the zero-sources header block and `No listings found. Done.`  <!-- event-driven -->

**Independent Test**: Golden stdout test compares full captured baseline; CLI unit tests assert flag parsing and the no-match path.

---

### P5: Unit Tests

**User Story**: As a maintainer, I want unit tests so that refactors and new feeds cannot silently break behavior.

**Why P5**: Requested explicitly ("Add unit tests").

**Acceptance Criteria**:

1. Tests SHALL cover scoring (hard reject, require-any, positive title/tech/domain keywords, remote/EU bonus, score cap, tiers) against `criteria.yaml` values  <!-- ubiquitous -->
2. Tests SHALL cover the seen store (mark, is_seen, filter_unseen, clear_all) against an isolated temp database via `JOBTRACKER_DATA_DIR`  <!-- ubiquitous -->
3. Tests SHALL cover digest formatting (empty input, strong/worth grouping, signal truncation to 5)  <!-- ubiquitous -->
4. Tests SHALL cover each feed's parsing logic network-free (mocked `urllib` responses or pure parse functions)  <!-- ubiquitous -->
5. The test suite SHALL NOT access the network and SHALL NOT read or write the production `data/seen.db`  <!-- ubiquitous -->

**Independent Test**: `poetry run pytest` passes with zero network access (verified by running with sockets mocked/unavailable in CI-less local run).

---

### P6: Architecture Documentation

**User Story**: As a maintainer, I want `ARCH.md` in the repo so that the architecture doc of record travels with the code.

**Why P6**: "Create a ARCH.md file and use it instead" (of the wiki page).

**Acceptance Criteria**:

1. The repo SHALL contain `ARCH.md` documenting: the vertical-slice structure, dependency rule, feed contract, step-by-step "add a new feed", the cron stdout contract, and config file roles  <!-- ubiquitous -->
2. `README.md` SHALL reference `ARCH.md` as the architecture doc (replacing the wiki pointer)  <!-- ubiquitous -->
3. The Obsidian wiki page SHALL point to the repo `ARCH.md` as the architecture doc of record  <!-- ubiquitous -->

**Independent Test**: Files exist and cross-reference correctly; wiki page diff shows the pointer swap.

---

## Edge Cases

Edge cases are usually unwanted-behavior (IF/THEN) or boundary (WHEN) criteria:

- IF a feed module raises during scrape THEN the pipeline SHALL continue with the remaining sources and the failing source contributes zero listings (per-feed try/except preserved)
- IF `sources.yaml` or `criteria.yaml` is missing THEN the program SHALL fail with a clear Python file-not-found error (current behavior; no new handling introduced)
- IF a scraped listing has an empty URL (HN comments) THEN the dedup store SHALL still track it (hash of empty string; current behavior preserved)
- WHEN two sources share the same feed type THEN the registry SHALL dispatch each with its own source entry (no cross-talk)

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story | Phase | Status |
| -------------- | ----------- | ------ | ------- |
| ARCH-01 | P1: Poetry Packaging | Design | Verified |
| ARCH-02 | P1: Poetry Packaging | Design | Verified |
| ARCH-03 | P1: Poetry Packaging | Design | Verified |
| ARCH-04 | P2: Vertical Feed Slices | Design | Pending |
| ARCH-05 | P2: Vertical Feed Slices | Design | Pending |
| ARCH-06 | P2: Vertical Feed Slices | Design | Pending |
| ARCH-07 | P2: Vertical Feed Slices | Design | Pending |
| ARCH-08 | P2: Vertical Feed Slices | Design | Pending |
| ARCH-09 | P2: Vertical Feed Slices | Design | Pending |
| ARCH-10 | P3: Shared Core | Design | Verified |
| ARCH-11 | P3: Shared Core | Design | Verified |
| ARCH-12 | P3: Shared Core | Design | Pending |
| ARCH-13 | P3: Shared Core | Design | Pending |
| ARCH-14 | P4: CLI Contract Parity | Design | Pending |
| ARCH-15 | P4: CLI Contract Parity | Design | Pending |
| ARCH-16 | P4: CLI Contract Parity | Design | Pending |
| ARCH-17 | P5: Unit Tests | Design | Verified |
| ARCH-18 | P5: Unit Tests | Design | Verified |
| ARCH-19 | P5: Unit Tests | Design | Verified |
| ARCH-20 | P5: Unit Tests | Design | Pending |
| ARCH-21 | P5: Unit Tests | Design | Pending |
| ARCH-22 | P5: Unit Tests | Design | Pending |
| ARCH-23 | P6: Architecture Documentation | Design | Pending |
| ARCH-24 | P6: Architecture Documentation | Design | Pending |
| ARCH-25 | P6: Architecture Documentation | Design | Pending |

**ID format:** `[CATEGORY]-[NUMBER]` (e.g., `AUTH-01`, `CART-03`, `NOTIF-02`)

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** 25 total, mapping completed in tasks.md, 0 unmapped

---

## Success Criteria

How we know the feature is successful:

- [ ] `poetry run pytest` green (zero failures) with the full suite network-free
- [ ] `/usr/bin/python3 main.py --source ramp --dry-run` byte-matches the golden baseline captured pre-refactor
- [ ] Adding a feed = 1 new module in `src/jobtracker/feeds/` + 1 `sources.yaml` entry, no other edits (demonstrated by test fixture)
- [ ] `main.py` entrypoint, flags, and stdout contract unchanged for the cron
- [ ] `ARCH.md` exists in-repo; README + wiki point to it
