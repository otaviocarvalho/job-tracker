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
| 12 | Anthropic | Greenhouse API | `board: anthropic` (trending) |
| 13 | Databricks | Greenhouse API | `board: databricks` (trending) |
| 14 | Stripe | Greenhouse API | `board: stripe` (trending) |
| 15 | GitLab | Greenhouse API | `board: gitlab` (trending) |
| 16 | Vercel | Greenhouse API | `board: vercel` (trending) |
| 17 | Together AI | Greenhouse API | `board: togetherai` (trending) |
| 18 | OpenAI | Ashby SSR payload | jobs.ashbyhq.com/openai (trending) |
| 19 | ElevenLabs | Ashby SSR payload | jobs.ashbyhq.com/elevenlabs (trending) |
| 20 | Lovable | Ashby SSR payload | jobs.ashbyhq.com/lovable (trending) |
| 21 | Perplexity | Ashby SSR payload | jobs.ashbyhq.com/perplexity (trending) |
| 22 | Harvey | Ashby SSR payload | jobs.ashbyhq.com/harvey (trending) |
| 23 | Polymarket | Ashby SSR payload | jobs.ashbyhq.com/polymarket (trending) |
| 24 | Replit | Ashby SSR payload | jobs.ashbyhq.com/replit (trending) |
| 25 | Anysphere (Cursor) | Manual check (captcha-gated) | cursor.com/careers |
| 26 | Kraken | Manual check (own ATS) | jobs.kraken.com |
| 27 | Revolut | Manual check (own ATS) | revolut.com/careers |
| 28 | ByteDance | Manual check (own ATS) | jobs.bytedance.com |
| 29 | Klarna | Manual check (own ATS) | klarna.com/careers |
| 30 | Canva | Manual check (own ATS) | canva.com/careers |
| 31 | Snyk | Manual check (own ATS) | careers.snyk.io |
| 32 | Hugging Face | Manual check (own ATS) | huggingface.co/Company/jobs |
| 33 | Deel | Manual check (empty Ashby board) | deel.com/careers |
| 34 | xAI | Greenhouse API | `board: xai` (trending; `location_include` London/EMEA/Remote International) |

Removed 2026-08-30: Sequoia, Index Ventures, Greylock Greenhouse boards (all 404; their job sites moved to JS-rendered ATS with no public API).

**Trending companies** (AD-0006): Setter30 late-stage pre-IPO watchlist added 2026-09-18. Sources with `config.trending: true` render under their own **TRENDING COMPANIES** digest section; companies with no recurrently scrapeable board (`type: report` + `trending: true`) render as a **TRENDING MANUAL CHECK** block (name + careers URL) so they still get explored by hand. Tier sections display at most 10 matches each, and at most `digest_max_per_company` (criteria.yaml, default 3) entries per company — the highest-scored ones — so a single employer cannot flood a section; the rest count toward the `(+N more above threshold, not shown)` footer (all truncation is display-only).

**Per-source location filter** (AD-0007, added 2026-10-06): a source entry may set `config.location_include` (list of substrings); the pipeline then keeps only listings whose `location` field matches at least one substring, case-insensitively, before scoring/dedup. Used for xAI (`london`, `united kingdom`, `ireland`, `dublin`, `emea`, `europe`, `remote international`) so its 300-job board contributes only the geographies Otavio actually wants.

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
