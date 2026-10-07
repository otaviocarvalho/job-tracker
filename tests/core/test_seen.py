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


def _backdate(url: str, days: int):
    conn = sqlite3.connect(str(seen._db_path()))
    try:
        conn.execute(
            "UPDATE seen SET first_seen = datetime('now', ?) WHERE url = ?",
            (f"-{days} days", url),
        )
        conn.commit()
    finally:
        conn.close()


def test_top_scores_orders_by_score_and_filters_window():
    seen.mark_seen("https://jobs/a", "A", company="Acme", source="s", score=60)
    seen.mark_seen("https://jobs/b", "B", company="Beta", source="s", score=90)
    seen.mark_seen("https://jobs/c", "C", company="Gamma", source="s", score=99)
    _backdate("https://jobs/c", 120)  # first seen outside the 90-day window

    top = seen.top_scores(days=90, limit=10)

    assert [t["title"] for t in top] == ["B", "A"]
    assert top[0]["company"] == "Beta"
    assert top[0]["first_seen"]  # timestamp string present for the digest


def test_top_scores_respects_limit():
    for i in range(15):
        seen.mark_seen(f"https://jobs/{i}", f"T{i}", company=f"C{i}", score=i)

    top = seen.top_scores(days=90, limit=5)

    assert len(top) == 5
    assert top[0]["title"] == "T14"  # highest score first


def test_top_scores_caps_per_company():
    for i in range(5):
        seen.mark_seen(f"https://jobs/a{i}", f"A{i}", company="Flood", score=100 - i)
    seen.mark_seen("https://jobs/b", "B", company="Beta", score=95)
    seen.mark_seen("https://jobs/g", "G", company="Gamma", score=90)

    top = seen.top_scores(days=90, limit=10)

    flood = [t for t in top if t["company"] == "Flood"]
    assert len(flood) == 3  # cap before the overall limit
    assert len(top) == 5  # 3 Flood + Beta + Gamma
    assert top[0]["company"] == "Flood" and top[0]["score"] == 100
    assert [t["company"] for t in top if t["company"] != "Flood"] == ["Beta", "Gamma"]


def test_top_scores_empty_db_returns_empty_list(isolated_db):
    assert seen.top_scores() == []
