# ARCH.md - Job Tracker Architecture

The architecture doc of record for this repo. It replaces the Architecture section of the Obsidian wiki page (`obsidian-otavio/wiki/projects/Job Tracker`), which now points here. The wiki keeps the curated source wishlist and profile notes; this file owns the technical truth.

## What it is

A standalone CLI that scrapes curated job feeds, scores listings against Otavio's profile, dedups via SQLite, and prints a markdown digest to stdout. A Hermes cron (`e61ce479c5ee`, every 6h) runs it and relays the digest to Telegram. Code and scheduling are decoupled: the tracker knows nothing about Hermes; Hermes knows nothing about scraping.

```
main.py -> cli -> pipeline -> registry -> feeds/* -> core/*
                     └───────────────────────────────^
```

Dependency rule (enforced by `tests/core/test_imports.py`):

- `core` imports nothing from `feeds`, `registry`, `pipeline`, or `cli`
- `feeds` may import `core` (config loader) and `registry` (decorator)
- `registry` never imports `feeds`; registration flows through the decorator, and `pipeline` imports `jobtracker.feeds` once to trigger discovery

## Layout: vertical feature slices

```
job-tracker/
├── ARCH.md                    # this file
├── README.md                  # quick start, feeds table, cron setup
├── pyproject.toml             # poetry: pyyaml (runtime), pytest (dev)
├── poetry.lock
├── main.py                    # thin shim: src/ bootstrap + cli.main()  [CRON ENTRYPOINT]
├── config/
│   ├── sources.yaml           # feed registry input: name / type / url / config
│   └── criteria.yaml          # profile weights, reject rules, thresholds
├── data/
│   └── seen.db                # SQLite dedup state (gitignored)
└── src/jobtracker/
    ├── cli.py                 # argparse: --reset / --source / --dry-run
    ├── pipeline.py            # orchestration: scrape -> score -> dedup -> digest -> mark seen
    ├── registry.py            # @register(type) + type -> scrape fn map + scrape_source()
    ├── core/                  # shared kernel (no feed knowledge)
    │   ├── config.py          # repo_root(), load_sources(), load_criteria()
    │   ├── scoring.py         # keyword scoring, hard rejects, tiers (strong 70 / worth 45)
    │   ├── seen.py            # SQLite dedup; JOBTRACKER_DATA_DIR overrides the data dir
    │   └── digest.py          # markdown digest renderer
    └── feeds/                 # VERTICAL SLICES: one self-contained module per feed type
        ├── __init__.py        # pkgutil auto-discovery: imports every module below
        ├── greenhouse.py      # Greenhouse boards API (a16z portfolio)
        ├── hackernews.py      # HN "Who's Hiring" via Algolia
        ├── infranyc.py        # infra.nyc (Next.js RSC payload extraction)
        ├── report.py          # manual-review sources (Ramp, Harmonic, FYSK): no scraping
        ├── speedrun.py        # a16z Speedrun Talent Network JSON API
        ├── substack.py        # Substack RSS (Next Play, Early Days, a16z Build)
        └── ycombinator.py     # YC Work at a Startup (Inertia data-page payloads)
```

Each feed slice is vertical: it owns its fetching, its parsing, and its registration. There is no shared HTTP layer on purpose. Real feeds have bespoke quirks (Inertia payloads, RSC streams, UA-gated 406s, politeness sleeps); keeping those inside the slice makes every change local.

## The feed contract

A feed module in `src/jobtracker/feeds/`:

```python
from jobtracker.registry import register

@register("<type>")            # matches the "type" key in config/sources.yaml
def scrape(source: dict) -> list[dict]:
    # source = the full YAML entry: {"name", "type", "url", "config"}
    ...
    return [{"title", "company", "url", "location", "description", "source"}, ...]
```

- Returns the standardized listing dict above. Build a synthetic `description` from whatever structured fields the source offers so the keyword matcher can score it.
- On any error: print `  [<feed>:<id>] Error: <e>` and return `[]`. Never raise; one dead feed must not kill the digest.
- Registration is automatic. `feeds/__init__.py` walks the package with `pkgutil` and imports every module; the `@register` decorator does the rest. No dispatcher to edit.

## How to add a new feed

1. Probe the source with HTTP only (curl/python, no browser): prefer public JSON API, then embedded JSON in HTML, then RSS.
2. Prototype the extraction until you get sane listing counts and field shapes.
3. Write `src/jobtracker/feeds/<name>.py` following the contract above.
4. Add one entry to `config/sources.yaml` with `type: <name>`.
5. Unit-test the parsing network-free (mock `urllib.request.urlopen` or test pure parse helpers), then run `python main.py --source <name> --dry-run` (read-only; a real run marks listings seen irreversibly).
6. `poetry run pytest`, commit, and keep the README feeds table in sync.

That is the whole integration: one new module + one YAML line.

## Pipeline phases

`pipeline.run()` (invoked by `main.py`):

1. **Scrape** every source from `sources.yaml` (optionally filtered by `--source <name substring>`, case-insensitive) via `registry.scrape_source`. Unknown types print `  Unknown source type: <type>` and contribute nothing.
2. **Score** with `core.scoring` against `criteria.yaml`: hard rejects (frontend/EM/devops...), require-any title keyword, positive title/tech/domain points, remote +10 / EU +8, capped at 100. Tiers: strong >= 70, worth >= 45; only those survive.
3. **Dedup** with `core.seen` (SQLite by URL hash; empty URLs hash too).
4. **Digest** sorted by score desc, grouped STRONG MATCH then WORTH A LOOK.
5. **Mark seen** unless `--dry-run`. `--reset` wipes dedup state first.

## The cron contract (do not break)

The Hermes job runs `cd ~/code/job-tracker && /usr/bin/python3 main.py 2>/dev/null` and greps stdout for the digest section. Therefore:

- `main.py` stays at the repo root and bootstraps `src/` onto `sys.path` itself: the cron needs no poetry env and no installed package.
- Runtime dependencies stay stdlib + PyYAML (already available to the system python).
- Stdout text is frozen. `tests/test_cli.py` byte-matches golden captures of `--source ramp --dry-run` (deterministic: report feed, no network, no dedup writes). If you intentionally change output wording, regenerate the goldens and update the cron prompt in the same change.
- Switching the cron to `poetry run` would be a separate decision; today it is unnecessary.

## Testing

- `poetry install` once, then `poetry run pytest` (76 tests).
- The suite never touches the network: every feed test mocks `urllib.request.urlopen` or tests pure parse helpers.
- The suite never touches the production `data/seen.db`: set `JOBTRACKER_DATA_DIR` (all store/pipeline tests do; it overrides the data directory at call time).
- Golden CLI tests double as the cron-contract gate; run the full check with `/usr/bin/python3 main.py --source ramp --dry-run` and compare against the embedded golden in `tests/test_cli.py`.
