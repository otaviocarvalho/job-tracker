"""SQLite-based dedup store. Tracks seen listings by URL hash per search group.

Schema v2 (AD-0008): the primary key is (url_hash, group_name), so each
search group keeps an independent dedup state - the same listing can be new
in one group and already-seen in another. v1 databases (single url_hash key,
no group_name column) migrate in place on first connection: every row is
preserved under group 'global' with its original first_seen timestamp.
"""
import hashlib
import os
import sqlite3
from pathlib import Path

from .config import load_criteria, repo_root

DEFAULT_DB_PATH = repo_root() / "data" / "seen.db"

DEFAULT_GROUP = "global"

_FALLBACK_MAX_PER_COMPANY = 3

_CREATE_SEEN = """
    CREATE TABLE IF NOT EXISTS seen (
        url_hash TEXT NOT NULL,
        group_name TEXT NOT NULL DEFAULT 'global',
        url TEXT NOT NULL,
        title TEXT NOT NULL,
        company TEXT,
        source TEXT,
        score INTEGER,
        first_seen TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (url_hash, group_name)
    )
"""


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


def _migrate_v1_to_v2(conn: sqlite3.Connection):
    """v1 (url_hash primary key) -> v2 composite key, in place.

    Every existing row moves under the 'global' group and keeps its
    first_seen timestamp. SQLite DDL is transactional, so a failure here
    leaves the v1 table untouched.
    """
    conn.execute("ALTER TABLE seen RENAME TO seen_v1")
    conn.execute(_CREATE_SEEN)
    conn.execute(
        """
        INSERT OR IGNORE INTO seen
            (url_hash, group_name, url, title, company, source, score, first_seen)
        SELECT url_hash, 'global', url, title, company, source, score, first_seen
        FROM seen_v1
        """
    )
    conn.execute("DROP TABLE seen_v1")


def _connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(seen)").fetchall()}
    if not cols:
        conn.execute(_CREATE_SEEN)
    elif "group_name" not in cols:
        _migrate_v1_to_v2(conn)
    conn.commit()
    return conn


def _hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def is_seen(url: str, group: str = DEFAULT_GROUP) -> bool:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT 1 FROM seen WHERE url_hash = ? AND group_name = ?",
            (_hash(url), group),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def mark_seen(
    url: str,
    title: str,
    company: str = "",
    source: str = "",
    score: int = 0,
    group: str = DEFAULT_GROUP,
):
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO seen (url_hash, group_name, url, title, company, source, score) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_hash(url), group, url, title, company, source, score),
        )
        conn.commit()
    finally:
        conn.close()


def filter_unseen(listings: list[dict], group: str = DEFAULT_GROUP) -> list[dict]:
    """Return only listings whose URL hasn't been seen before in this group."""
    result = []
    for listing in listings:
        if not is_seen(listing["url"], group):
            result.append(listing)
    return result


def mark_all_seen(listings: list[dict], group: str = DEFAULT_GROUP):
    """Mark multiple listings as seen for one group."""
    for listing in listings:
        mark_seen(
            listing["url"],
            listing.get("title", ""),
            listing.get("company", ""),
            listing.get("source", ""),
            listing.get("score", 0),
            group,
        )


def top_scores(
    days: int = 90,
    limit: int = 10,
    max_per_company: int | None = None,
    group: str = DEFAULT_GROUP,
) -> list[dict]:
    """Highest-scored listings first seen within the last `days` days, per group.

    Feeds the digest highlights: everything above threshold ever marked
    seen lives in this table with its score, so this is the group's 90-day
    leaderboard.
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
                WHERE first_seen >= datetime('now', ?) AND group_name = ?
            )
            WHERE rn <= ?
            ORDER BY score DESC, first_seen DESC
            LIMIT ?
            """,
            (f"-{int(days)} days", group, int(max_per_company), int(limit)),
        )
        cols = ("title", "company", "source", "score", "url", "first_seen")
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def clear_all():
    """Wipe the dedup table across ALL groups (for testing/reset)."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM seen")
        conn.commit()
    finally:
        conn.close()
