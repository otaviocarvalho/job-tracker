"""Job Tracker - Main CLI entrypoint.

Usage:
    python main.py              # Full cycle: scrape -> filter -> dedup -> output
    python main.py --reset      # Clear dedup DB and run fresh
    python main.py --source X   # Run only one source by name
    python main.py --dry-run    # Scrape and score but don't mark seen
"""
import sys
from pathlib import Path

# Make the jobtracker package importable without installation: the Hermes
# cron runs this file directly with the system python (no poetry env).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from jobtracker.cli import main

if __name__ == "__main__":
    main()
