# Search Groups Tasks

## Task Breakdown

### Phase 1

### T1: Group config loader

**Status**: done

Add `load_groups()` to `src/jobtracker/core/config.py`: reads
`config/groups.yaml` (`groups:` list), normalizes each entry to
`{name, label, require_location_keywords (lowered list), sources (list or None),
trending_manual (bool)}`; missing/empty file falls back to
`[{"name": "global", "label": "Global"}]`. Ship `config/groups.yaml` with the
three production groups: `global` (label Global, trending_manual true, no
gate), `emea` (label EMEA, EMEA keyword gate), `spain-bcn` (label
"Spain Remote + Barcelona", spain/barcelona/espana/españa gate) (GRP-01,
GRP-08).

**Tests**: unit (`tests/core/test_config.py`): parse real shipped yaml (3
groups, ordered names, labels, gates non-empty, global has no gate +
trending_manual); missing-file fallback via monkeypatched `CONFIG_DIR`;
keyword lowering + label defaulting.

**Gate**: `.venv/bin/python -m pytest -q` (worktree `~/code/job-tracker.groups`)

**Depends on**: none

### T2: Group-scoped dedup store + v1->v2 migration

`src/jobtracker/core/seen.py`: table v2 = columns `(url_hash, group_name NOT
NULL DEFAULT 'global', url, title, company, source, score, first_seen,
PRIMARY KEY (url_hash, group_name))`; `_connect()` creates v2 on fresh DBs and
migrates v1 in place (rename -> create -> INSERT SELECT with 'global' ->
drop, preserving `first_seen`). Every public function gains
`group: str = "global"` (`is_seen`, `mark_seen`, `filter_unseen`,
`mark_all_seen`, `top_scores` adds `WHERE group_name = ?`); `clear_all`
wipes all groups (GRP-02, GRP-03).

**Tests**: unit (`tests/core/test_seen.py`): per-group isolation (mark
global does not make emea seen); both groups can hold the same url_hash;
top_scores filtered by group; migration test seeds a v1 file then checks
rows preserved under global with original first_seen and emea still unseen;
fresh DB has composite PK; rerun of migration on v2 is a no-op.

**Gate**: `.venv/bin/python -m pytest -q` (worktree)

**Depends on**: T1

### T3: Digest group block

`digest.format_digest` gains `group_label: str = ""`; when set, prints
`**<label>**` between the title line and notes (GRP-06). No other rendering
change; default call sites stay byte-identical.

**Tests**: unit (`tests/core/test_trending.py`): block with label renders the
label line; without label, output identical to today.

**Gate**: `.venv/bin/python -m pytest -q` (worktree)

**Depends on**: T1

### Phase 2

### T4: Pipeline multi-group run

`pipeline.run` gains `group_filter: str = ""`: loads groups (substring filter,
case-insensitive; no match -> print `No group matches filter: <f>` and return
""), scrapes once with unchanged phase banners, then per group: source
subset, `filter_by_group` word-boundary location gate (empty location dropped
when gate set; prints `  [<name>] Group filter: kept K, dropped D outside
<terms>` when it drops), scoring, per-group dedup, per-group highlights
(`top_scores(group=...)`), labeled digest block; MANUAL CHECK only when
`trending_manual`; collect blocks, print one DIGEST header + blocks separated
by a blank line, then per-group mark-seen with
`Marked N listings as seen (<name>).` (GRP-04, GRP-05, GRP-06). Update the
two phase-order test lambdas to accept `group_label`.

**Tests**: unit (`tests/test_pipeline.py`): gate drops non-matching/empty
locations and prints the filter line; same listing new in two groups renders
in both and marks both; already-seen in global does not suppress emea;
group_filter selects subsets; sources subset honored; dry-run marks nothing;
per-group trending_manual.

**Gate**: `.venv/bin/python -m pytest -q` (worktree)

**Depends on**: T2, T3

### T5: CLI flag + goldens

`cli.py` adds `--group` (default "") forwarded to `run`. Regenerate the
golden constants in `tests/test_cli.py` (plain report-only path now renders
three labeled group blocks; MANUAL CHECK only under Global) and update
README.md cron section for the three per-group crons + ARCH.md (groups
concept, pipeline phases, cron contract, seen schema) + AGENTS.md cron
command wording (GRP-07, docs of record).

**Tests**: golden (`tests/test_cli.py`): regenerated goldens pin the new
output shape; cli unit: `--group` forwarded; unknown group -> message, no
DIGEST.

**Gate**: `.venv/bin/python -m pytest -q` (worktree)

**Depends on**: T4

### T6: Spec decision log + STATE

Record AD-0008 (search groups: config shape, per-group dedup, migration
policy, cron-per-group wiring) in `.specs/STATE.md` decisions and refresh its
handoff snapshot; final spec traceability status pass.

**Tests**: none (docs-only; validation is the state gate)

**Gate**: `.venv/bin/python -m pytest -q` (worktree) + `.specs/` docs diff reviewed

**Depends on**: T5

## Execution Plan

```text
T1 -> T2
T1 -> T3
T2 -> T4
T3 -> T4
T4 -> T5
T5 -> T6
```

### Phase 1: T1, T2, T3 (foundation: config, store, digest label)

### Phase 2: T4, T5, T6 (pipeline, CLI + goldens, decision log)

## Test Coverage Matrix

| Requirement ID | Test(s) |
| -------------- | ------- |
| GRP-01 | tests/core/test_config.py::test_load_groups_shipped_yaml, ::test_load_groups_missing_file_fallback, ::test_load_groups_normalization |
| GRP-02 | tests/core/test_seen.py::test_group_isolation, ::test_same_url_two_groups, ::test_top_scores_by_group |
| GRP-03 | tests/core/test_seen.py::test_v1_migration_preserves_rows_and_first_seen, ::test_migration_idempotent_on_v2, ::test_fresh_db_composite_pk |
| GRP-04 | tests/test_pipeline.py::test_group_gate_drops_non_matching_and_empty, ::test_no_gate_passes_all |
| GRP-05 | tests/test_pipeline.py::test_same_listing_two_groups, ::test_global_seen_does_not_block_emea, ::test_group_filter_selects_subset, ::test_sources_subset_honored, ::test_dry_run_marks_nothing |
| GRP-06 | tests/core/test_trending.py::test_group_label_line, ::test_manual_check_only_when_flagged + tests/test_pipeline.py::test_trending_manual_flag |
| GRP-07 | tests/test_cli.py::test_group_flag_forwarded, ::test_unknown_group_no_digest + regenerated goldens |
| GRP-08 | tests/core/test_config.py::test_load_groups_shipped_yaml |

## Gate Check Commands

```bash
cd ~/code/job-tracker.groups
.venv/bin/python -m pytest -q > /tmp/gate.log 2>&1; echo exit=$?; tail -1 /tmp/gate.log
# gate floor at HEAD before T1: 107 passed, exit=0
```
