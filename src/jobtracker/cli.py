"""CLI entrypoint: argparse + pipeline invocation.

Kept byte-compatible with the legacy main.py interface - the Hermes cron
greps stdout and the flags are frozen (see ARCH.md).
"""
import argparse

from jobtracker.pipeline import run


def main():
    parser = argparse.ArgumentParser(description="Job Tracker")
    parser.add_argument("--reset", action="store_true", help="Clear dedup DB")
    parser.add_argument("--source", type=str, default="", help="Filter by source name")
    parser.add_argument("--dry-run", action="store_true", help="Don't mark listings as seen")

    args = parser.parse_args()
    run(reset=args.reset, source_filter=args.source, dry_run=args.dry_run)
