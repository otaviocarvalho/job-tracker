# Job Tracker

Automated job position tracker that scrapes curated startup/tech job sources, filters for roles matching a profile, and outputs a digest.

## Quick Start

```bash
cd ~/code/job-tracker
python main.py              # full cycle
python main.py --dry-run    # don't mark seen
python main.py --reset      # clear dedup DB
python main.py --source HN  # only HN source
```

## Architecture

See `~/code/obsidian-otavio/wiki/projects/Job Tracker/Job Tracker.md`

## Dependencies

- Python 3.10+ (stdlib only: urllib, json, sqlite3, xml, argparse)
- PyYAML (`pip install pyyaml`)
