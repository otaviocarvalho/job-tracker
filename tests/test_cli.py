"""CLI contract tests (ARCH-20/21): golden stdout byte-match + flag forwarding.

The golden strings are regenerated for the always-report output: every run
ends in a DIGEST block with execution notes + the 90-day highlights, even
with zero raw listings. The only nondeterministic part (the wall-clock
timestamp in the digest header) is normalized before comparison. The Hermes
cron greps for the DIGEST header - it must never move.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

from jobtracker import cli

REPO_ROOT = Path(__file__).resolve().parents[1]
SEP = "=" * 60

# The digest header carries datetime.now(); mask it so the golden is stable.
TS_RE = re.compile(r"Job Tracker Digest - \w{3} \d{2}, \d{2}:\d{2}")
TS_TOKEN = "Job Tracker Digest - <TIMESTAMP>"

GOLDEN_REPORT_ONLY = f"""
{SEP}
Scraping 1 source(s)...
{SEP}

> Ramp Vendor Reports (report)
  [report:Ramp Vendor Reports] Report-type sources need manual review: https://ramp.com/data
  Got 0 raw listings

Total raw listings: 0
No listings found. Done.
  [global] 0 above threshold | 0 new
  [global] No new listings. Done.
  [emea] 0 above threshold | 0 new
  [emea] No new listings. Done.
  [spain-bcn] 0 above threshold | 0 new
  [spain-bcn] No new listings. Done.

{SEP}
DIGEST
{SEP}

{TS_TOKEN}
**Global**
Run: 1 source(s) | 0 raw | 0 above threshold | 0 new

**HIGHLIGHTS: top scores, last 90 days**
Nothing tracked yet.

No new matches this run: everything above threshold was already reported.


{TS_TOKEN}
**EMEA**
Run: 1 source(s) | 0 raw | 0 above threshold | 0 new

**HIGHLIGHTS: top scores, last 90 days**
Nothing tracked yet.

No new matches this run: everything above threshold was already reported.


{TS_TOKEN}
**Spain Remote + Barcelona**
Run: 1 source(s) | 0 raw | 0 above threshold | 0 new

**HIGHLIGHTS: top scores, last 90 days**
Nothing tracked yet.

No new matches this run: everything above threshold was already reported.

"""

GOLDEN_NO_MATCH = f"""
{SEP}
Scraping 0 source(s)...
{SEP}

Total raw listings: 0
No listings found. Done.
  [global] 0 above threshold | 0 new
  [global] No new listings. Done.
  [emea] 0 above threshold | 0 new
  [emea] No new listings. Done.
  [spain-bcn] 0 above threshold | 0 new
  [spain-bcn] No new listings. Done.

{SEP}
DIGEST
{SEP}

{TS_TOKEN}
**Global**
Run: 0 source(s) | 0 raw | 0 above threshold | 0 new

**HIGHLIGHTS: top scores, last 90 days**
Nothing tracked yet.

No new matches this run: everything above threshold was already reported.


{TS_TOKEN}
**EMEA**
Run: 0 source(s) | 0 raw | 0 above threshold | 0 new

**HIGHLIGHTS: top scores, last 90 days**
Nothing tracked yet.

No new matches this run: everything above threshold was already reported.


{TS_TOKEN}
**Spain Remote + Barcelona**
Run: 0 source(s) | 0 raw | 0 above threshold | 0 new

**HIGHLIGHTS: top scores, last 90 days**
Nothing tracked yet.

No new matches this run: everything above threshold was already reported.

"""


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
    assert TS_RE.sub(TS_TOKEN, proc.stdout) == GOLDEN_REPORT_ONLY


def test_golden_no_matching_source(tmp_path):
    proc = _run_main(tmp_path, "--source", "zzznonexistent", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert TS_RE.sub(TS_TOKEN, proc.stdout) == GOLDEN_NO_MATCH


def test_cli_flags_forward_to_pipeline(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli, "run", lambda reset, source_filter, dry_run, group_filter="": captured.update(
            reset=reset, source_filter=source_filter, dry_run=dry_run, group_filter=group_filter
        )
    )
    monkeypatch.setattr(
        "sys.argv", ["main.py", "--reset", "--source", "HN", "--group", "emea", "--dry-run"]
    )

    cli.main()

    assert captured == {
        "reset": True, "source_filter": "HN", "dry_run": True, "group_filter": "emea"
    }


def test_cli_defaults_forward_empty(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli, "run", lambda reset, source_filter, dry_run, group_filter="": captured.update(
            reset=reset, source_filter=source_filter, dry_run=dry_run, group_filter=group_filter
        )
    )
    monkeypatch.setattr("sys.argv", ["main.py"])

    cli.main()

    assert captured == {
        "reset": False, "source_filter": "", "dry_run": False, "group_filter": ""
    }
