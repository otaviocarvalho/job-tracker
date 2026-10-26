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


def test_group_isolation_mark_global_does_not_mark_emea():
    """GRP-02: dedup state is per group."""
    seen.mark_seen("https://jobs/x", "X", "Acme", "test", 80)
    assert seen.is_seen("https://jobs/x") is True  # global (default)
    assert seen.is_seen("https://jobs/x", group="emea") is False
    assert seen.is_seen("https://jobs/x", group="spain-bcn") is False
    seen.mark_seen("https://jobs/x", "X", "Acme", "test", 80, group="emea")
    assert seen.is_seen("https://jobs/x", group="emea") is True
    assert seen.is_seen("https://jobs/x", group="spain-bcn") is False


def test_same_url_can_live_in_two_groups(isolated_db):
    """GRP-02/03: composite PK (url_hash, group_name) allows the same url_hash twice."""
    seen.mark_seen("https://jobs/x", "X", score=80)
    seen.mark_seen("https://jobs/x", "X", score=80, group="emea")
    rows = sqlite3.connect(str(isolated_db / "seen.db")).execute(
        "SELECT group_name FROM seen WHERE url_hash = ?", (seen._hash("https://jobs/x"),)
    ).fetchall()
    assert sorted(r[0] for r in rows) == ["emea", "global"]


def test_filter_unseen_and_mark_all_seen_are_group_scoped():
    listings = [{"url": "https://jobs/a", "title": "A", "company": "C", "source": "s", "score": 70}]
    seen.mark_all_seen(listings, group="emea")
    assert seen.filter_unseen(listings, group="emea") == []
    assert [l["url"] for l in seen.filter_unseen(listings, group="global")] == ["https://jobs/a"]


def test_top_scores_by_group():
    seen.mark_seen("https://jobs/g1", "Global Job", "Acme", "test", 90)
    seen.mark_seen("https://jobs/e1", "EMEA Job", "Beta", "test", 85, group="emea")

    assert [t["url"] for t in seen.top_scores(days=90, limit=10)] == ["https://jobs/g1"]
    assert [t["url"] for t in seen.top_scores(days=90, limit=10, group="emea")] == ["https://jobs/e1"]
    assert seen.top_scores(days=90, limit=10, group="spain-bcn") == []


def test_v1_migration_preserves_rows_and_first_seen(isolated_db):
    """GRP-03: v1 db (url_hash PK only) migrates in place under 'global'."""
    v1 = sqlite3.connect(str(isolated_db / "seen.db"))
    v1.execute(
        """
        CREATE TABLE seen (
            url_hash TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT,
            source TEXT,
            score INTEGER,
            first_seen TEXT DEFAULT (datetime('now'))
        )
        """
    )
    v1.execute(
        "INSERT INTO seen (url_hash, url, title, company, source, score, first_seen) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (seen._hash("https://jobs/old"), "https://jobs/old", "Old Job", "Legacy", "test", 66, "2026-09-01 10:00:00"),
    )
    v1.commit()
    v1.close()

    # Any read/write through the store triggers the migration.
    assert seen.is_seen("https://jobs/old") is True
    assert seen.is_seen("https://jobs/old", group="emea") is False
    seen.mark_seen("https://jobs/emea-new", "New", group="emea")

    conn = sqlite3.connect(str(isolated_db / "seen.db"))
    row = conn.execute(
        "SELECT group_name, first_seen, score FROM seen WHERE url_hash = ?",
        (seen._hash("https://jobs/old"),),
    ).fetchone()
    conn.close()
    assert row == ("global", "2026-09-01 10:00:00", 66)

    top = seen.top_scores(days=90, limit=10)
    assert [t["title"] for t in top] == ["Old Job"]  # migrated row counts for global


def test_migration_is_noop_on_v2(isolated_db):
    seen.mark_seen("https://jobs/a", "A", score=50)
    seen._connect()  # second connect: v2 already, no rewrite, no error
    seen.mark_seen("https://jobs/b", "B", score=51)
    assert seen.is_seen("https://jobs/a") and seen.is_seen("https://jobs/b")


def test_fresh_db_uses_composite_pk(isolated_db):
    seen.mark_seen("https://jobs/a", "A")
    conn = sqlite3.connect(str(isolated_db / "seen.db"))
    info = conn.execute("PRAGMA table_info(seen)").fetchall()
    conn.close()
    pk_cols = [r[1] for r in sorted(info, key=lambda r: r[5]) if r[5] > 0]
    assert pk_cols == ["url_hash", "group_name"]
