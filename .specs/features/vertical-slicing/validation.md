# Validation Report: vertical-slicing

Verifier: independent (author ≠ verifier). Scope: diff range `6f59994..HEAD` (8 commits: 218ae7e → d0d1c32) on branch `refactor/vertical-slicing` in `/home/otavio/code/job-tracker-arch`. Method: spec-anchored evidence check against `.specs/features/vertical-slicing/spec.md` (24 ACs), deterministic build gate, 3-mutation discrimination sensor in a scratch worktree. No production tree files were modified (this report is the only artifact written).

## Verdict: PASS

All 24 ACs matched with file:line evidence; build gate green (76 passed, exit 0); all 3 injected mutants killed by their targeted tests. Zero surviving mutants, zero ACs lacking evidence. One recorded SPEC_DEVIATION (T5 `_TAG_RE` fix) judged properly documented, per scope.

## Gate

- `poetry run pytest -q` → **exit=0**, summary line: **`76 passed in 0.43s`** (expected 76 passed — exact match).
- Smoke `/usr/bin/python3 main.py --source ramp --dry-run` (cwd = repo root, bare system python, no install): printed the report-only block — `> Ramp Vendor Reports (report)` header, `[report:Ramp Vendor Reports] Report-type sources need manual review: https://ramp.com/data` notice, `Got 0 raw listings`, `Total raw listings: 0`, ending **`No listings found. Done.`** — and produced **no DIGEST block**. Deterministic and digest-free as required.

## Discrimination Sensor

Method: manual scratch (per tightened scope — NOT sensor_mutants.py, because the poetry editable install points at the real tree). One scratch worktree `/tmp/jt-sensor` at HEAD (d0d1c32), reused for all three mutations with a revert after each (`git checkout -- <file>`). Run recipe: `PYTHONPATH=/tmp/jt-sensor/src JOBTRACKER_DATA_DIR=/tmp/jt-sensor-data <poetry env python> -m pytest <node> -q`. Import provenance was explicitly verified before M1 (`import jobtracker.core.scoring` resolved to `/tmp/jt-sensor/src/jobtracker/core/scoring.py`), so tests exercised the mutant tree, not the real one. Baseline `git status --porcelain` captured before start; final status matched the baseline (only this report file untracked) — no drift. Worktree removed and `/tmp/jt-sensor-data` deleted afterward.

| # | Mutation | file:line | Description | Target test | Result |
|---|----------|-----------|-------------|-------------|--------|
| 1 | Score cap removed | src/jobtracker/core/scoring.py:88 | `min(score, 100)` → `min(score, 200)` | tests/core/test_scoring.py::test_score_capped_at_100 | killed (1 failed, `assert 150 == 100`) |
| 2 | Dry-run guard removed | src/jobtracker/pipeline.py:77 | `if not dry_run:` → `if True or dry_run:` (mark-seen always runs) | tests/test_pipeline.py::test_dry_run_does_not_mark_seen | caught (1 failed, AssertionError) |
| 3 | Unknown-type message changed | src/jobtracker/registry.py:46 | `Unknown source type: {stype}` → `[registry] Unrecognized feed type: {stype}` | tests/test_registry.py::test_scrape_source_unknown_type_prints_and_returns_empty | caught (1 failed) |

Summary: 3 injected, 3 killed, 0 survived. All runs collected and executed exactly one test each (no collection errors, no "no tests ran" — all kills valid). Anchors were found exactly as specified; no adjustments needed.

## AC Evidence Table (24 ACs)

| AC | Spec outcome | Evidence (file:line + assertion) | Result |
|----|--------------|----------------------------------|--------|
| ARCH-01 | poetry env with pyyaml + pytest dev group, locked | pyproject.toml:1-13 (`[tool.poetry]` + dev group pytest ^8.0); poetry.lock exists (repo root, verified); tests/test_smoke.py:4 `test_package_imports` + :10 `test_runtime_dependency_pyyaml_present` | PASS |
| ARCH-02 | PyYAML only runtime dep, Python >=3.11 | pyproject.toml:9 `python = "^3.11"`, :10 `pyyaml = "^6.0"` — the only entries under `[tool.poetry.dependencies]` | PASS |
| ARCH-03 | entrypoint runs without pip-installed package | main.py:14 `sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))` + :16 `from jobtracker.cli import main`; golden subprocess tests tests/test_cli.py:43/:49 run via bare interpreter | PASS |
| ARCH-04 | one self-contained module per feed under feeds/ | src/jobtracker/feeds/{greenhouse,hackernews,infranyc,report,speedrun,substack,ycombinator}.py (ARCH.md:43-51 layout); tests/feeds/test_discovery.py:11-12 `assert registry.registered_types() == EXPECTED_TYPES` (7 types) | PASS |
| ARCH-05 | zero-touch discovery of new module | tests/feeds/test_discovery.py:15-33 — writes `zz_discovery_probe.py` with `@register('zzprobe')`, `importlib.reload(feeds)`, asserts `"zzprobe" in registry.registered_types()` with no edits elsewhere | PASS |
| ARCH-06 | dispatch passes full source entry | src/jobtracker/registry.py:36-45 `scrape_source(source)` → `return fn(source)`; tests/test_registry.py:33 `test_scrape_source_passes_full_source_entry_to_feed` | PASS |
| ARCH-07 | unknown type prints message, returns empty | src/jobtracker/registry.py:46 `print(f"  Unknown source type: {stype}")` + `return []`; tests/test_registry.py:55 unknown-type test, :60 missing-type-key test (`stype == ""` path) | PASS |
| ARCH-08 | listing contract + error convention | tests/feeds/test_greenhouse.py:45-52 full dict equality `{title, company, url, location, description, source}`; :60-65 error → `assert greenhouse.scrape(SOURCE) == []` + `"[greenhouse:a16z] Error:"` in stdout; tests/feeds/test_speedrun.py:53 synthetic-body error test with same convention | PASS |
| ARCH-09 | report notice preserved | tests/feeds/test_report.py:5 `test_report_prints_manual_review_notice_and_returns_empty` | PASS |
| ARCH-10 | core never imports outward | tests/core/test_imports.py:36 `test_core_never_imports_outward_layers`; additionally tests/test_registry.py:65 `test_registry_module_never_imports_feeds` | PASS |
| ARCH-11 | JOBTRACKER_DATA_DIR override | tests/core/test_seen.py:18-20 `assert seen._db_path() == isolated_db / "seen.db"` + `assert not seen._db_path().is_relative_to(repo_root())` | PASS |
| ARCH-12 | single criteria loader; ycombinator uses it | tests/core/test_config.py:28 `test_load_criteria_values_used_by_scoring`; tests/feeds/test_ycombinator.py:82 `test_enrichment_keywords_come_from_shared_criteria_loader` + :89 `test_enrichment_keywords_fallback_when_criteria_unavailable` | PASS |
| ARCH-13 | pipeline order + dry-run skip | tests/test_pipeline.py:99 `test_phase_order_scrape_score_dedup_digest_mark`; :113 `test_dry_run_phase_order_skips_mark` | PASS |
| ARCH-14 | entrypoint + identical flags | main.py:18-19 `main()`; flags `--reset/--source/--dry-run` (cli.py, documented ARCH.md:35); tests/test_cli.py:55 `test_cli_flags_forward_to_pipeline`, :69 `test_cli_defaults_forward_empty` | PASS |
| ARCH-15 | golden byte-match report-only | tests/test_cli.py:17 `GOLDEN_REPORT_ONLY = (` captured baseline constant; :43 `test_golden_report_only_dry_run_byte_matches_pre_refactor` | PASS |
| ARCH-16 | no-match source path | tests/test_cli.py:49 `test_golden_no_matching_source` | PASS |
| ARCH-17 | scoring coverage | tests/core/test_scoring.py — exactly 9 tests (count verified programmatically): reject / require-any / keywords / remote+EU / cap / tiers / filter | PASS |
| ARCH-18 | seen coverage | tests/core/test_seen.py — exactly 7 tests (count verified): roundtrip, filter_unseen, mark_all_seen, empty URL, idempotent insert, clear_all, env override; module docstring cites ARCH-18 | PASS |
| ARCH-19 | digest coverage | tests/core/test_digest.py — exactly 6 tests (count verified): empty input :18, header/counts :22, strong-before-worth :29, block content :34, truncation-to-5 :41, other-tier-only :49 | PASS |
| ARCH-20 | per-feed parsing network-free | tests/feeds/conftest.py:11-43 `FakeResponse`/`urlopen_returning`/`urlopen_raising` fakes; every feed scrape test monkeypatches `urllib.request.urlopen` (e.g. test_greenhouse.py:40); HN parse tests are pure functions (test_hackernews.py:8-36) | PASS |
| ARCH-21 | suite no network, never touches prod data/seen.db | tests/feeds/conftest.py:1-6 docstring "the suite never hits the network" + fakes; tests/core/test_seen.py:12-15 autouse `isolated_db` fixture sets `JOBTRACKER_DATA_DIR` to tmp_path; tests/test_cli.py:33 `_run_main` sets `env["JOBTRACKER_DATA_DIR"] = str(tmp_path)  # the suite never touches the production seen.db` | PASS |
| ARCH-22 | ARCH.md with required topics | ARCH.md — structure:20 (vertical slice layout), dependency rule:38 (`core/ shared kernel (no feed knowledge)`), feed contract:56, add-a-feed:74, pipeline phases:85, cron contract:95, testing policy:104 | PASS |
| ARCH-23 | README references ARCH.md | README.md:85 `## Architecture`; :87 "See [ARCH.md](ARCH.md). It is the architecture doc of record …"; :89 `## Dependencies` | PASS |
| ARCH-24 | wiki points to repo ARCH.md | commit `299205f` "docs: point Job Tracker architecture at repo ARCH.md" (found in obsidian-otavio history via `git log --oneline --all`; READ-ONLY); wiki `wiki/projects/Job Tracker/Job Tracker.md`:104 "Architecture doc of record (2026-09-05): the repository owns it now: `ARCH.md` in otaviocarvalho/job-tracker … The repo doc wins on conflicts." | PASS |

Result: **24/24 ACs matched, 0 spec-precision gaps.**

## Task Completion (T1-T8)

| Task | Title | Status | Verifier evidence |
|------|-------|--------|-------------------|
| T1 | Poetry packaging scaffold | complete | pyproject.toml:1-13, poetry.lock, tests/test_smoke.py:4/:10 |
| T2 | Extract core config + scoring kernel | complete | src/jobtracker/core/{config,scoring}.py; tests/core/test_config.py, test_scoring.py (9 tests) |
| T3 | Extract dedup store + digest with test isolation | complete | tests/core/test_seen.py (7 tests, isolated_db), test_digest.py (6 tests) |
| T4 | Feed registry with decorator + dispatch | complete | src/jobtracker/registry.py:16/:31/:36; tests/test_registry.py (7 tests) |
| T5 | Vertical feed slices with auto-discovery | complete | src/jobtracker/feeds/*.py; tests/feeds/test_discovery.py; SPEC_DEVIATION recorded below |
| T6 | Pipeline + CLI cutover, remove legacy layers | complete | src/jobtracker/pipeline.py + cli.py; tests/test_pipeline.py, tests/test_cli.py; legacy `src/scrapers|filters|store|output` gone from layout (ARCH.md:34-51) |
| T7 | ARCH.md + README architecture pointer | complete | ARCH.md (7 sections), README.md:85-89 |
| T8 | Wiki pointer swap + live full-cycle verification | complete | obsidian commit 299205f + wiki line 104; live smoke run green (Gate section) |

## Code Quality

| Area | Assessment |
|------|------------|
| Slice design | Each feed module owns fetch/parse/registration; no shared HTTP layer by explicit decision (ARCH.md:54). Registry is 46 lines, thin and readable. |
| Dependency rule | core has no feed/pipeline knowledge, enforced by two import-lint tests (test_imports.py:36, test_registry.py:65) — good: architecture constraint is regression-guarded. |
| Test hygiene | Isolation via autouse fixture + explicit env in subprocess helper; network fakes shared in conftest.py rather than duplicated. 76 tests in 0.43s — consistent with zero I/O beyond tmp dirs. |
| Contract preservation | Golden byte-match test (test_cli.py:17/:43) pins the cron stdout contract; smoke run independently confirms it. |
| Minor observations (non-blocking) | test_discovery.py zero-touch test writes into the real feeds/ package dir and cleans up in `finally` — acceptable, self-cleaning; `registry._REGISTRY` poked directly in cleanup — acceptable for a test. |

## Edge Cases

- **Feed raise isolation** (spec line 153): every feed's error path returns `[]` and prints `  [<feed>:<id>] Error: ...` instead of raising — tests/feeds/test_greenhouse.py:60-65, test_speedrun.py:53, test_infranyc.py:75, test_substack.py:57, test_hackernews.py:58.
- **Missing YAML propagation** (spec line 154): loaders used directly with no new exception handling (tests/core/test_config.py:12/:28 exercise the real `config/*.yaml` path); no handling was added — current fail-loud behavior preserved per spec.
- **Empty-URL dedup** (spec line 155): tests/core/test_seen.py:48-51 `test_empty_url_listing_is_still_tracked` — `seen.mark_seen("", ...)` then `assert seen.is_seen("") is True` (hash of empty string keys it).
- **Same feed type twice** (spec line 156): dispatch is per-source-entry — `scrape_source(source)` forwards the full dict each call (src/jobtracker/registry.py:36-45; tests/test_registry.py:33 asserts the full entry is passed), so two sources sharing a type get independent entries. No dedicated two-sources-same-type test exists; covered structurally (noted as minor, not an AC).

## Deviations

- **T5 SPEC_DEVIATION (pre-recorded, judged properly documented)**: `feeds/hackernews.py::_TAG_RE` fixed to `r"<[^>]+>"` — the closing `>` was missing in the old `src/scrapers/hackernews.py`, so tag stripping left stray `>` characters. tasks.md:215 records it verbatim with the reason ("tests derived from the spec's parsing intent exposed the latent typo; one-char fix, flagged to Otavio in the final report"). Per scope, this is judged only on documentation quality: **properly documented — accepted**. It is a one-char behavior fix in a latent bug, consistent with the spec's parsing intent, not a stealth scope change.

## Gaps

None. No AC lacks evidence; no mutant survived; gate matches the expected 76 passed exactly.
