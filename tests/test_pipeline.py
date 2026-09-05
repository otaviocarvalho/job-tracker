"""Pipeline orchestration tests (ARCH-14..16): phase order, dry-run, reset, filter."""
import pytest
from jobtracker import pipeline
from jobtracker.core import seen

SOURCES = [
    {"name": "S1", "type": "t1", "url": "u1"},
    {"name": "S2", "type": "t2", "url": "u2"},
]

STRONG = {
    "title": "Staff Platform Engineer",
    "company": "Acme",
    "url": "https://jobs/strong",
    "location": "Remote",
    "description": "Kafka Kubernetes",
    "source": "S1",
}  # staff 20 + platform 15 + kafka 15 + kubernetes 10 + remote 10 = 70 -> strong

WORTH = {
    "title": "Senior Platform Engineer",
    "company": "Acme",
    "url": "https://jobs/worth",
    "location": "Barcelona",
    "description": "Kafka",
    "source": "S1",
}  # 30 + kafka 15 + eu 8 = 53 -> worth

WEAK = {
    "title": "Junior Engineer",
    "company": "Acme",
    "url": "https://jobs/weak",
    "location": "",
    "description": "",
    "source": "S1",
}  # 0 -> weak, filtered before dedup


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBTRACKER_DATA_DIR", str(tmp_path))


def test_full_flow_scores_dedups_and_marks_seen(monkeypatch):
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES)
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(STRONG), dict(WEAK)])

    out = pipeline.run()

    assert "STRONG MATCH" in out
    assert "Staff Platform Engineer" in out
    assert "Junior Engineer" not in out  # below worth threshold
    assert seen.is_seen("https://jobs/strong") is True
    assert seen.is_seen("https://jobs/weak") is False  # never reached dedup


def test_dry_run_does_not_mark_seen(monkeypatch):
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES)
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(STRONG)])

    out = pipeline.run(dry_run=True)

    assert out is not None and "Staff Platform Engineer" in out
    assert seen.is_seen("https://jobs/strong") is False


def test_second_run_dedups_to_nothing(monkeypatch, capsys):
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES)
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(STRONG)])

    pipeline.run()
    out = pipeline.run()

    assert out is None
    assert "No new listings. Done." in capsys.readouterr().out


def test_reset_clears_dedup_state(monkeypatch, capsys):
    seen.mark_seen("https://jobs/strong", "Staff Platform Engineer")
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES)
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [])

    assert pipeline.run(reset=True) is None

    assert seen.is_seen("https://jobs/strong") is False
    assert "Clearing dedup database..." in capsys.readouterr().out


def test_source_filter_is_case_insensitive_substring(monkeypatch):
    scraped = []
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES)
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: scraped.append(s["name"]) or [])

    pipeline.run(source_filter="s1")

    assert scraped == ["S1"]


def test_phase_order_scrape_score_dedup_digest_mark(monkeypatch):
    events = []
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: events.append("scrape") or [dict(STRONG)])
    monkeypatch.setattr(pipeline.matcher, "filter_and_score", lambda ls: events.append("score") or ls)
    monkeypatch.setattr(pipeline.seen, "filter_unseen", lambda ls: events.append("dedup") or ls)
    monkeypatch.setattr(pipeline.digest, "format_digest", lambda ls: events.append("digest") or "DIGEST")
    monkeypatch.setattr(pipeline.seen, "mark_all_seen", lambda ls: events.append("mark"))

    pipeline.run()

    assert events == ["scrape", "score", "dedup", "digest", "mark"]


def test_dry_run_phase_order_skips_mark(monkeypatch):
    events = []
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: events.append("scrape") or [dict(STRONG)])
    monkeypatch.setattr(pipeline.matcher, "filter_and_score", lambda ls: events.append("score") or ls)
    monkeypatch.setattr(pipeline.seen, "filter_unseen", lambda ls: events.append("dedup") or ls)
    monkeypatch.setattr(pipeline.digest, "format_digest", lambda ls: events.append("digest") or "DIGEST")
    monkeypatch.setattr(pipeline.seen, "mark_all_seen", lambda ls: events.append("mark"))

    pipeline.run(dry_run=True)

    assert events == ["scrape", "score", "dedup", "digest"]


def test_digest_sorted_by_score_desc(monkeypatch):
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES)
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(WORTH), dict(STRONG)])

    out = pipeline.run()

    # strong (70) listed before worth (53) regardless of scrape order
    assert out.index("Staff Platform Engineer") < out.index("Senior Platform Engineer")
