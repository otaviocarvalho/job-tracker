# Validation Report - search-groups

## Verdict: PASS

PASS — all GRP-01..GRP-08 acceptance criteria covered by named tests, all 5 required adversarial mutations killed, final gate 135/135 green (exit 0), live-config sanity runs clean.

## Gate

- Baseline at HEAD (0623e3b) before Task 1: 107 passed, exit 0.
- Final gate: **135 passed, exit 0** (`.venv/bin/python -m pytest -q` in the worktree).
- Live-config sanity (temp `JOBTRACKER_DATA_DIR`, dry-run): `--group emea` opens the block with `**EMEA**`, 930 raw / 124 above threshold; `--group zzz` prints `No group matches filter: zzz` and renders no DIGEST section, exit 0.
- Realistic v1 migration probe: 3-row v1 DB (distinct `first_seen`) -> all rows preserved under group `global` with `first_seen` byte-intact, PK becomes `(url_hash, group_name)`, cross-group reads stay isolated.

## Adversarial verification (independent Verifier sub-agent)

Required mutations (all applied to the worktree, gate run, then reverted; gate re-confirmed green after each revert):

| Mutation | Target | Result |
|---|---|---|
| M1 | `seen._migrate_v1_to_v2` drops `first_seen` in the copy | KILLED (migration preservation test fails) |
| M2 | `pipeline.filter_by_group` passes everything through | KILLED (4 fails) |
| M3 | `seen` ignores the group param (hardcoded 'global') | KILLED (9 fails) |
| M4 | `cli` drops `group_filter` forwarding | KILLED (flag-forward test fails) |
| M5 | `digest` skips the group-label line | KILLED (7 fails, incl. both goldens) |

AC coverage: GRP-01..GRP-08 each pinned by named tests (see Verifier output; goldens pin the DIGEST grep anchor, block shape, and blank-line separation).

## Findings fixed after verification

1. `clear_all()` scope (GRP-02) was unpinned - a `DELETE ... WHERE group_name='global'` mutation survived. Fixed: `test_seen.py::test_clear_all_wipes_every_group`.
2. `--group` case-insensitivity (GRP-07) was unpinned. Fixed: `test_pipeline.py::test_group_filter_is_case_insensitive_substring` (filter `EMEA` matches).
3. Spec edge case "v1 DB with zero rows" had no test. Fixed: `test_seen.py::test_v1_db_with_zero_rows_migrates_cleanly`.
4. Spec said `name` is required while the loader synthesizes `group-<n>` when missing. Fixed: spec wording updated to document the fallback (implementation unchanged - it is the friendlier behavior).

Hazard note (documented, no defect): gate keywords must start/end with word characters or the `\b...\b` wrapping silently never matches; current `config/groups.yaml` complies.

## Environment reality checks

- Tests never touch the network and never touch production `data/seen.db` (`JOBTRACKER_DATA_DIR` everywhere).
- `--dry-run` marks nothing for any group (pinned by `test_dry_run_leaves_every_group_unmarked`).
- All work happened in the `/home/otavio/code/job-tracker.groups` worktree; the production checkout was only advanced with `git pull --rebase` after the merge.
