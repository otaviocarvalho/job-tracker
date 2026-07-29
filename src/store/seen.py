"""SQLite-based dedup store. Tracks seen listings by URL hash."""
import sqlite3
import hashlib
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "seen.db"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
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


def clear_all():
    """Wipe the dedup table (for testing/reset)."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM seen")
        conn.commit()
    finally:
        conn.close()
