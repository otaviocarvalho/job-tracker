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
Every day at 8am, run the job tracker and deliver the digest if there are
new matches. Execute: cd ~/code/job-tracker && /usr/bin/python3 main.py
2>/dev/null. If the output contains a "DIGEST" section with job listings,
send the digest text as-is. If it says "No new listings", send nothing
(stay silent). Do NOT send debug output or scraping logs.
```

### Option B: CLI slash command (exact, as currently deployed)

```
/cron add "0 8 * * *" "Run the job tracker and deliver the digest if there are new matches.

Execute: \`cd ~/code/job-tracker && /usr/bin/python3 main.py 2>/dev/null\`

If the output contains \"DIGEST\" section with job listings, send the digest text as-is.
If the output says \"No new listings\" or \"No listings above threshold\", send nothing (stay silent).
Do NOT send debug output or scraping logs — only send the formatted digest that appears after the \"DIGEST\" header."
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
- PyYAML, declared and locked via poetry (`pyproject.toml` / `poetry.lock`); the cron runs `main.py` with the system python, so PyYAML must stay available there
- Dev: pytest via the poetry dev group (`poetry run pytest`)
