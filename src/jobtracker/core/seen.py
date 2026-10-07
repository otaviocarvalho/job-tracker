"""SQLite-based dedup store. Tracks seen listings by URL hash."""
import hashlib
import os
import sqlite3
from pathlib import Path

from .config import load_criteria, repo_root

DEFAULT_DB_PATH = repo_root() / "data" / "seen.db"

_FALLBACK_MAX_PER_COMPANY = 3


def _max_per_company() -> int:
    """criteria.yaml `digest_max_per_company`, or 3 if unreadable (same as digest)."""
    try:
        return int(load_criteria().get("digest_max_per_company", _FALLBACK_MAX_PER_COMPANY))
    except Exception:
        return _FALLBACK_MAX_PER_COMPANY


def _db_path() -> Path:
    """Dedup DB location. JOBTRACKER_DATA_DIR overrides the directory (test isolation)."""
    override = os.environ.get("JOBTRACKER_DATA_DIR")
    if override:
        return Path(override) / "seen.db"
    return DEFAULT_DB_PATH


def _connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            url_hash TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT,
            source TEXT,
            score INTEGER,
            first_seen TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def _hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def is_seen(url: str) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("SELECT 1 FROM seen WHERE url_hash = ?", (_hash(url),))
        return cur.fetchone() is not None
    finally:
        conn.close()


def mark_seen(url: str, title: str, company: str = "", source: str = "", score: int = 0):
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO seen (url_hash, url, title, company, source, score) VALUES (?, ?, ?, ?, ?, ?)",
            (_hash(url), url, title, company, source, score),
        )
        conn.commit()
    finally:
        conn.close()


def filter_unseen(listings: list[dict]) -> list[dict]:
    """Return only listings whose URL hasn't been seen before."""
    result = []
    for listing in listings:
        if not is_seen(listing["url"]):
            result.append(listing)
    return result


def mark_all_seen(listings: list[dict]):
    """Mark multiple listings as seen."""
    for listing in listings:
        mark_seen(
            listing["url"],
            listing.get("title", ""),
            listing.get("company", ""),
            listing.get("source", ""),
            listing.get("score", 0),
        )


def top_scores(
    days: int = 90, limit: int = 10, max_per_company: int | None = None
) -> list[dict]:
    """Highest-scored listings first seen within the last `days` days.

    Feeds the digest highlights: everything above threshold ever marked
    seen lives in this table with its score, so this is the 90-day leaderboard.
    `max_per_company` (default: criteria.yaml `digest_max_per_company`, 3) caps
    how many rows one company can contribute before the overall limit, applied
    in SQL so a single large board cannot own the whole candidate pool.
    """
    if max_per_company is None:
        max_per_company = _max_per_company()
    conn = _connect()
    try:
        cur = conn.execute(
            """
            SELECT title, company, source, score, url, first_seen
            FROM (
                SELECT title, company, source, score, url, first_seen,
                       ROW_NUMBER() OVER (
                           PARTITION BY company COLLATE NOCASE
                           ORDER BY score DESC, first_seen DESC
                       ) AS rn
                FROM seen
                WHERE first_seen >= datetime('now', ?)
            )
            WHERE rn <= ?
            ORDER BY score DESC, first_seen DESC
            LIMIT ?
            """,
            (f"-{int(days)} days", int(max_per_company), int(limit)),
        )
        cols = ("title", "company", "source", "score", "url", "first_seen")
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def clear_all():
    """Wipe the dedup table (for testing/reset)."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM seen")
        conn.commit()
    finally:
        conn.close()
