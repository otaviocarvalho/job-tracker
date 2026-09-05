"""Dedup store tests (ARCH-18). Every test runs against an isolated temp DB
via JOBTRACKER_DATA_DIR (AD-0004): the production data/seen.db is never touched.
"""
import sqlite3

import pytest

from jobtracker.core import seen
from jobtracker.core.config import repo_root


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBTRACKER_DATA_DIR", str(tmp_path))
    return tmp_path


def test_db_path_respects_env_override(isolated_db):
    assert seen._db_path() == isolated_db / "seen.db"
    assert not seen._db_path().is_relative_to(repo_root())


def test_mark_and_is_seen_roundtrip():
    assert seen.is_seen("https://jobs/x/1") is False
    seen.mark_seen("https://jobs/x/1", "Backend Engineer", "Acme", "test", 55)
    assert seen.is_seen("https://jobs/x/1") is True


def test_filter_unseen_returns_only_new():
    seen.mark_seen("https://jobs/old", "Old", score=50)
    listings = [
        {"url": "https://jobs/old", "title": "Old", "company": "A", "source": "s", "score": 50},
        {"url": "https://jobs/new", "title": "New", "company": "B", "source": "s", "score": 60},
    ]
    result = seen.filter_unseen(listings)
    assert [l["url"] for l in result] == ["https://jobs/new"]


def test_mark_all_seen_persists_every_listing():
    listings = [
        {"url": "https://jobs/1", "title": "One", "company": "A", "source": "s", "score": 70},
        {"url": "https://jobs/2", "title": "Two", "company": "B", "source": "s", "score": 45},
    ]
    seen.mark_all_seen(listings)
    assert seen.is_seen("https://jobs/1") and seen.is_seen("https://jobs/2")


def test_empty_url_listing_is_still_tracked():
    # spec edge case: HN comments carry empty URLs; hash("") keys them
    seen.mark_seen("", "HN comment posting")
    assert seen.is_seen("") is True


def test_mark_seen_is_idempotent_insert_or_ignore():
    seen.mark_seen("https://jobs/x", "First Title", score=10)
    seen.mark_seen("https://jobs/x", "Second Title", score=99)

    conn = sqlite3.connect(str(seen._db_path()))
    try:
        rows = conn.execute("SELECT url, title, score FROM seen WHERE url = 'https://jobs/x'").fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0][1] == "First Title"  # first insert wins
    assert rows[0][2] == 10


def test_clear_all_wipes_state():
    seen.mark_seen("https://jobs/1", "One")
    seen.clear_all()
    assert seen.is_seen("https://jobs/1") is False
