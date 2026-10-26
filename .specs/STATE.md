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

### AD-0006: Trending companies watchlist (Setter30) with manual-check fallback (active, 2026-09-18)

Added the Setter30 late-stage pre-IPO companies as a "trending" watchlist. Design: `config.trending: true` on a source entry splits its new listings into a dedicated **TRENDING COMPANIES** digest section (scored exactly like everything else — no separate criteria); companies with no recurrently scrapeable board (captcha-gated SPA, empty/filtered ATS board, own careers site with no public API) are `type: report` + `trending: true` and render as a static **TRENDING MANUAL CHECK** block (name + careers URL) in every full run, so they are explored by hand. Trackable boards: Greenhouse API (anthropic, databricks, stripe, gitlab, vercel, togetherai) + new `ashby` feed slice. Key discovery: Ashby's public posting API returns 401, but the board page is SSR'd with the full job list in an inline `window.__appData` JSON blob — plain urllib (browser UA) gets it where browsers hit CAPTCHA (that is how OpenAI/Perplexity/Replit/Polymarket/Harvey became trackable). Ashby SSR omits job bodies, so descriptions are synthetic (title/team/workplace/locations/comp) — fewer tech-keyword points, hence fewer Ashby listings cross the worth bar; that is accepted, not a bug to game. Tier sections cap display at 10 per tier with a `(+N more above threshold, not shown)` footer (display-only truncation; scoring/dedup keep full shape) — needed because a first run floods 600+ matches and the digest goes to Telegram (4096-char messages). The plain no-trending no-listings digest wording is unchanged, so the cron goldens stayed byte-identical without regeneration.

### AD-0007: xAI source + per-source location filter + per-company digest cap (active, 2026-10-06)

Three related changes from Otavio's watchlist feedback ("too many Anthropic positions, limit per company; start crawling xAI jobs London/EMEA and remote"):

1. **xAI on Greenhouse** (`board: xai`, trending watchlist). Board verified live 2026-10-06: 302 jobs, mostly Memphis/Palo Alto. The merged SpaceX/XAI entity self-reports `company_name: "SpaceXAI"` on the board. Entry shared by Otavio (Software Engineer - X Money, London) resolves to `job-boards.greenhouse.io/xai`.
2. **`config.location_include`** (pipeline-level, `pipeline.filter_by_location`): optional per-source list of substrings; listings whose `location` field contains none of them are dropped right after scraping, before scoring/dedup (so unwanted geographies never burn dedup state). xAI uses `london, united kingdom, ireland, dublin, emea, europe, remote international` — bare `remote` deliberately excluded so "Remote US" stays out; 302 raw → 40 kept at verification time. Sources without the key are untouched.
3. **`digest_max_per_company`** (criteria.yaml, default 3, `digest.cap_per_company`): display-only cap per company per tier section (TRENDING COMPANIES and NEW MATCHES), keeping the highest-scored entries; hidden entries count toward the existing `(+N more above threshold, not shown)` footer. Scoring/dedup keep the full shape — a capped-out employer's remaining roles are still marked seen and never re-reported. Highlights block unchanged.

Cron stdout contract untouched: same DIGEST shape, footer wording unchanged, goldens (report-only path) byte-identical without regeneration.

### AD-0008: Search groups - parallel trackers over the same feeds (active, 2026-10-26)

Otavio asked for an EMEA-only tracker and a Spain remote + Barcelona tracker in parallel to the existing global one. Design: `config/groups.yaml` defines named groups; each group = `label` + optional `require_location_keywords` (word-boundary gate on `location`, `pipeline.filter_by_group`; empty location = dropped for gated groups) + optional `sources` subset + optional `trending_manual` flag (only `global` renders the MANUAL CHECK block - triplicate spam otherwise). The pipeline scrapes every source ONCE per run and fans the raw pool out to all groups; each group scores, dedups and digests independently. `core.seen` schema v2: primary key `(url_hash, group_name)` - the same listing can be new in `emea` while already reported in `global`; v1 databases migrate in place on first connection (every existing row moves under `global`, `first_seen` preserved, transactional rename-copy-drop). `--group <substring>` (cli, forwarded to `pipeline.run(group_filter=...)`) runs a subset; plain `main.py` runs all groups in one output (one DIGEST header, labeled `**<label>**` blocks). Deployed wiring: one Hermes cron per group (`--group global` on the existing job `e61ce479c5ee`, new jobs for `--group emea` and `--group spain-bcn`, same 6h cadence, same delivery thread) - separate jobs keep each digest under the Telegram 4096-char limit and give each group an independent dedup space. Goldens regenerated for the 3-group no-listing shape; first `emea`/`spain-bcn` run backfills (everything gate-passing is new for the fresh group), afterwards quiet. Keyword lists live in `config/groups.yaml` and are meant to be tuned there, not in code.

## Handoff Snapshot

- **Feature**: search-groups (AD-0008) delivered and verified: 3 shipped groups (`global`, `emea`, `spain-bcn`), group-scoped dedup with v1->v2 migration, `--group` flag, goldens regenerated (132 tests green)
- **Cron**: one Hermes job per group - `e61ce479c5ee` (global) plus `Job Tracker EMEA` and `Job Tracker Spain` running `main.py --group <name>` every 6h; each greps the DIGEST header and relays to the job-listings thread
- **Next step**: none pending; tune group location keywords in `config/groups.yaml` (not in code); if the cron ever fails with a missing interpreter, run `poetry install` in the repo root
