# Job Tracker

Automated job position tracker that scrapes curated startup/tech job sources, filters for roles matching a profile, and outputs a digest.

**Repo:** https://github.com/otaviocarvalho/job-tracker

## Quick Start

```bash
cd ~/code/job-tracker
poetry install                        # one-time setup (creates env, installs pyyaml + pytest)
poetry run python main.py             # full cycle
poetry run python main.py --dry-run   # don't mark seen
poetry run python main.py --reset     # clear dedup DB
poetry run python main.py --source HN # only HN source
poetry run pytest                     # unit tests
```

The Hermes cron does not use poetry: it runs `main.py` directly with the system python (see the cron contract in ARCH.md).

## Data Feeds

Active sources (see `config/sources.yaml`):

| # | Source | Type | Endpoint |
|---|--------|------|----------|
| 1 | a16z Portfolio | Greenhouse API | `board: a16z` via portfolio-jobs.a16z.com |
| 2 | Y Combinator Jobs | YC startup directory scraper | ycombinator.com/jobs |
| 3 | HN Who's Hiring | Algolia HN API | news.ycombinator.com (whoishiring thread) |
| 4 | Next Play Newsletter | Substack RSS | nextplay.substack.com |
| 5 | Early Days Newsletter | Substack RSS | earlydaysbymerlin.substack.com |
| 6 | a16z Build Newsletter | Substack RSS | a16zbuild.substack.com |
| 7 | Speedrun Talent Network | a16z Speedrun jobs API | speedrun-talent-network.com/api/v1/jobs |
| 8 | infra.nyc | Curated board scraper | infra.nyc/jobs |
| 9 | Ramp Vendor Reports | Manual/periodic check | ramp.com/data |
| 10 | Harmonic Hot 25 | Manual/periodic check | harmonic.ai/hot-25-startups |
| 11 | Founders You Should Know | Manual/periodic check | foundersysk.com |

Removed 2026-08-30: Sequoia, Index Ventures, Greylock Greenhouse boards (all 404; their job sites moved to JS-rendered ATS with no public API).

Manual-check sources (`type: report`) are listed for reference only; they are not scraped automatically.

## Adding the Scheduled Job to Hermes

The tracker runs on a Hermes cron job (runs on this machine via the gateway daemon). Two ways to register it:

### Option A: Chat command (natural language)

Tell Hermes in any session:

```
Every 6 hours, run the job tracker and deliver the report. Execute:
cd ~/code/job-tracker && .venv/bin/python main.py 2>/dev/null. Send everything
from the "DIGEST" header onward as-is: it always carries the execution notes
line and the top-scores highlight of the last 90 days; a "NEW MATCHES" section
appears only when there are new listings. Respond [SILENT] only if the command
fails or prints no DIGEST section. Do NOT send debug output or scraping logs.
```

### Option B: CLI slash command (exact, as currently deployed)

```
/cron add "0 */6 * * *" "Run the job tracker and deliver the report.

Execute: \`cd ~/code/job-tracker && .venv/bin/python main.py 2>/dev/null\`

Send everything from the \"DIGEST\" header onward, as-is: the report always includes the execution notes line and the top-scores highlight of the last 90 days; a NEW MATCHES section appears only when there are new listings.
If the command fails or prints no DIGEST section, respond with exactly \"[SILENT]\".
Do NOT send debug output or scraping logs."
```

Notes:

- Cron jobs run in a **fresh session** with no memory, so the prompt must be fully self-contained (paths, commands, delivery rules).
- Requires the Hermes gateway running (`hermes gateway status`); install it with `hermes gateway install` if needed.
- `deliver: origin` sends the digest back to the chat/thread that created the job; use `deliver: telegram` for the home channel.
- Restrict toolsets with `enabled_toolsets: [terminal]` (as the live job does) to keep the cron run minimal.

### Current live job

- **Job ID:** `e61ce479c5ee` (name: "Job Tracker")
- **Schedule:** every 360 minutes (6h) — change with `/cron update e61ce479c5ee` or ask Hermes conversationally
- **Delivery:** origin (Hermes & Renato group, job listings thread)
- **Manage:** `/cron list`, `/cron pause <id>`, `/cron remove <id>` or `hermes cron list` from the shell

## Architecture

See [ARCH.md](ARCH.md). It is the architecture doc of record (vertical feed slices, registry, feed contract, cron contract). The Obsidian wiki page (`obsidian-otavio/wiki/projects/Job Tracker`) keeps the curated source wishlist and profile notes and points here for architecture.

## Dependencies

- Python 3.11+ (stdlib: urllib, json, sqlite3, xml, argparse)
- PyYAML, declared and locked via poetry (`pyproject.toml` / `poetry.lock`); the cron runs `main.py` with the repo venv (`.venv/bin/python`, created by `poetry install`), system python with PyYAML remains a fallback
- Dev: pytest via the poetry dev group (`.venv/bin/python -m pytest`)
