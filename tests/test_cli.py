"""CLI contract tests (ARCH-20/21): golden stdout byte-match + flag forwarding.

The golden strings are the exact stdout captured from pre-refactor master
(--source ramp --dry-run is deterministic: report-type feed, no network,
no dedup writes). The Hermes cron greps this output - it must never move.
"""
import os
import subprocess
import sys
from pathlib import Path

from jobtracker import cli

REPO_ROOT = Path(__file__).resolve().parents[1]
SEP = "=" * 60

GOLDEN_REPORT_ONLY = (
    f"\n{SEP}\nScraping 1 source(s)...\n{SEP}\n\n"
    "> Ramp Vendor Reports (report)\n"
    "  [report:Ramp Vendor Reports] Report-type sources need manual review: https://ramp.com/data\n"
    "  Got 0 raw listings\n\n"
    "Total raw listings: 0\nNo listings found. Done.\n"
)

GOLDEN_NO_MATCH = (
    f"\n{SEP}\nScraping 0 source(s)...\n{SEP}\n\n"
    "Total raw listings: 0\nNo listings found. Done.\n"
)


def _run_main(tmp_path, *args):
    env = os.environ.copy()
    env["JOBTRACKER_DATA_DIR"] = str(tmp_path)  # the suite never touches the production seen.db
    return subprocess.run(
        [sys.executable, "main.py", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )


def test_golden_report_only_dry_run_byte_matches_pre_refactor(tmp_path):
    proc = _run_main(tmp_path, "--source", "ramp", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == GOLDEN_REPORT_ONLY


def test_golden_no_matching_source(tmp_path):
    proc = _run_main(tmp_path, "--source", "zzznonexistent", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == GOLDEN_NO_MATCH


def test_cli_flags_forward_to_pipeline(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli, "run", lambda reset, source_filter, dry_run: captured.update(
            reset=reset, source_filter=source_filter, dry_run=dry_run
        )
    )
    monkeypatch.setattr("sys.argv", ["main.py", "--reset", "--source", "HN", "--dry-run"])

    cli.main()

    assert captured == {"reset": True, "source_filter": "HN", "dry_run": True}


def test_cli_defaults_forward_empty(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli, "run", lambda reset, source_filter, dry_run: captured.update(
            reset=reset, source_filter=source_filter, dry_run=dry_run
        )
    )
    monkeypatch.setattr("sys.argv", ["main.py"])

    cli.main()

    assert captured == {"reset": False, "source_filter": "", "dry_run": False}
