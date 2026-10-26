# Search Groups (Multi-Tracker) Specification

## Problem Statement

The tracker runs one global search: every feed is scored against the single
`criteria.yaml` profile and every listing shares one dedup store. Otavio wants
parallel trackers over the same feeds - one EMEA-only and one specific to
Spain remote + Barcelona - each with its own dedup state and its own digest,
without changing the global tracker's behavior or its Hermes cron contract.

## Goals

- [ ] Named search groups in `config/groups.yaml`; adding a group = editing YAML, zero code
- [ ] Per-group dedup: the same listing can be new in one group and already-seen in another
- [ ] v1 `seen.db` schemas migrate in place, preserving every row and its `first_seen`
- [ ] `main.py --group <name>` runs a subset; no flag runs all groups; existing flags untouched
- [ ] Shipped groups: `global` (today's behavior), `emea` (EMEA-only location gate),
      `spain-bcn` (Spain remote + Barcelona gate)

## Requirements

### GRP-01: Group configuration loader

- WHEN `config/groups.yaml` exists, the system SHALL load each entry under
  `groups:` as a dict with keys `name` (str, required; a missing name falls
  back to a synthesized `group-<n>` rather than erroring), `label` (str, default:
  `name`), `require_location_keywords` (list[str], lowercased, default: empty),
  `sources` (list[str] subset or empty for all), `trending_manual` (bool,
  default: false).
- IF `config/groups.yaml` is missing or empty, the system SHALL fall back to a
  single normalized group `{"name": "global", "label": "Global"}`.

### GRP-02: Per-group dedup store

- WHERE the `seen` table keys rows by `(url_hash, group_name)`, marking a URL
  as seen for one group SHALL NOT mark it seen for another group.
- WHEN reading/writing dedup state, every public function
  (`is_seen`, `mark_seen`, `filter_unseen`, `mark_all_seen`, `top_scores`)
  SHALL take a `group` parameter defaulting to `"global"`.
- WHILE `--reset` runs, `clear_all` SHALL wipe all groups.

### GRP-03: Schema migration v1 -> v2

- IF an existing `seen.db` has the v1 schema (primary key `url_hash` only, no
  `group_name` column), the first connection SHALL migrate it in place: every
  row is preserved under `group_name = 'global'` with its original
  `first_seen` timestamp.
- WHEN the database file is fresh or already v2, the system SHALL NOT rewrite it.

### GRP-04: Group location gate

- WHEN a group defines `require_location_keywords`, only listings whose
  `location` field matches at least one keyword SHALL survive into that
  group's scoring; matching SHALL be word-boundary, case-insensitive.
- IF a listing has an empty location and the gate is set, it SHALL be dropped
  for that group (a listing with no location cannot prove geography).
- WHEN the gate drops listings, the run SHALL print a per-group filter line
  with kept/dropped counts (execution notes only, before the DIGEST).
- WHERE a group has no `require_location_keywords`, all listings SHALL pass.

### GRP-05: Pipeline multi-group run

- WHEN `run()` executes, the system SHALL scrape every source ONCE (phase
  banners and per-source lines unchanged), then for each group in order:
  apply the group's source subset, the location gate, scoring, per-group
  dedup, digest block, and per-group mark-seen.
- IF `--dry-run` is set, NO group SHALL mark listings seen.
- WHEN a group's sources are restricted via `sources:`, listings from other
  sources SHALL not enter that group.

### GRP-06: Digest group block

- WHERE each group renders a digest block, the block SHALL start with the
  standard title line followed by a `**<label>**` group label line.
- WHEN a group does not set `trending_manual: true`, its block SHALL NOT
  render the TRENDING MANUAL CHECK section.
- WHEN multiple groups run, blocks SHALL be printed under one `DIGEST` header,
  separated by a blank line; stdout SHALL still end in the report.

### GRP-07: CLI group filter

- WHEN `--group <substr>` is passed, only groups whose `name` contains the
  substring (case-insensitive) SHALL run; existing flags (`--reset`,
  `--source`, `--dry-run`) SHALL keep their current meaning.
- IF the filter matches no group, the system SHALL print
  `No group matches filter: <substr>` and no DIGEST.

### GRP-08: Shipped group definitions

- `config/groups.yaml` SHALL ship exactly three groups: `global` (label
  Global, `trending_manual: true`, no gate), `emea` (label EMEA, EMEA
  location gate), `spain-bcn` (label Spain Remote + Barcelona, Spain/Barcelona
  location gate).

## Out of Scope

| Item | Reason |
| ---- | ------ |
| Group-specific scoring profiles/keywords | Same fit profile for all groups; scoring overrides come later if needed |
| Changing the global group's behavior | Cron contract must stay byte-stable apart from the label line |
| Per-group cron scheduling inside the repo | Cron wiring lives in Hermes; documented in README |
| New feeds | Sources stay as-is; groups filter, not feed |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| One cron per group, separate digest messages | `--group global` / `--group emea` / `--group spain-bcn` at staggered times | A 3-group single digest risks Telegram's 4096-char limit; separate messages keep each digest short and independently retryable | y (default) |
| Existing seen rows migrate under the `global` group | group_name='global' | The v1 store tracked exactly the global tracker's state | y |
| EMEA gate is strict: no location, no match | Drop unlocated listings | "EMEA only" means proven EMEA; HN posts without a location are excluded from the EMEA group only, still visible in Global | y (default) |
| Spain gate matches `spain`, `barcelona`, `espana`, `espana-accents` | Simple containment of Spain tokens | Location strings rarely encode remote-ness reliably; over-inclusion beats missing a "Barcelona or remote" listing; tighten YAML later if Madrid onsite noise bothers | y (default) |
| First EMEA/Spain runs backfill | Fat first digest (capped by digest tier limits) | Backfill shows the current EMEA/Spain candidate pool immediately; subsequent runs go quiet | y (default) |
| Word-boundary matching for gates | `\\b(keyword)\\b` on lowercased location | Substring would false-positive (`uk` in "Ukraine"); location field only, never description | y |

**Open questions:** none; defaults above are recorded and reversible via YAML.

## User Stories

### US-1: EMEA tracker (P1 - MVP)

As Otavio, I want a cron-delivered digest containing only EMEA jobs so that I
can scan European openings without US noise.

### US-2: Spain remote + Barcelona tracker (P1 - MVP)

As Otavio, I want a digest limited to Spain-flavored roles (remote in Spain or
Barcelona) so I can target my own geography.

### US-3: Maintainer adds a group (P2)

As a maintainer, I want to add a group by editing `config/groups.yaml` only,
so new regions need zero code changes.

## Edge Cases

- Listing with empty location under a gated group: dropped for that group only.
- Same URL new in two groups the same run: reported in both blocks; marked per group.
- v1 DB migration on a DB with zero rows: becomes an empty v2 table, no error.
- `--group` with unknown name: message + no DIGEST, exit 0.
- Group restricted to a `sources:` subset that matches nothing: empty block
  ("Run: 0 source(s) | 0 raw | ...") still renders.

## Success Criteria

- [ ] `poetry run pytest -q` green (existing 107 + new tests)
- [ ] A dry-run on a copy of the live `seen.db` migrates it: row count preserved,
      `first_seen` values preserved, all rows under `global`
- [ ] `main.py --source ramp --dry-run` (golden) shows all three group blocks,
      each labeled, MANUAL CHECK only in the Global block
- [ ] Global cron contract holds: stdout ends in the report starting at `DIGEST`

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| GRP-01 | US-3 | 1 | Implemented |
| GRP-02 | US-1, US-2 | 1 | Implemented |
| GRP-03 | US-1, US-2 | 1 | Implemented |
| GRP-04 | US-1, US-2 | 2 | Implemented |
| GRP-05 | US-1, US-2 | 2 | Implemented |
| GRP-06 | US-1, US-2 | 2 | Implemented |
| GRP-07 | US-3 | 2 | Implemented |
| GRP-08 | US-1, US-2 | 2 | Implemented |
