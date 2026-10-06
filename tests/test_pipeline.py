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

    # the report is always rendered, but with no NEW MATCHES section;
    # the first-run listing now shows up in the 90-day highlights instead
    assert out is not None
    assert "No new listings. Done." in capsys.readouterr().out
    assert "No new matches this run" in out
    assert "Staff Platform Engineer" in out  # highlight from seen.db
    assert "**NEW MATCHES**" not in out


def test_reset_clears_dedup_state(monkeypatch, capsys):
    seen.mark_seen("https://jobs/strong", "Staff Platform Engineer")
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES)
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [])

    out = pipeline.run(reset=True)

    assert out is not None  # report still renders after a reset
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
    monkeypatch.setattr(
        pipeline.digest, "format_digest",
        lambda ls, highlights=None, notes="", trending=None, trending_manual=None: events.append("digest") or "DIGEST",
    )
    monkeypatch.setattr(pipeline.seen, "mark_all_seen", lambda ls: events.append("mark"))

    pipeline.run()

    assert events == ["scrape", "score", "dedup", "digest", "mark"]


def test_filter_by_location_passes_through_without_config():
    src = {"name": "S1", "type": "t1", "url": "u1"}
    listings = [dict(STRONG), dict(WORTH)]
    assert pipeline.filter_by_location(src, listings) == listings


def test_filter_by_location_keeps_matching_locations_only(capsys):
    src = {
        "name": "xAI",
        "type": "greenhouse",
        "url": "u",
        "config": {"location_include": ["london", "remote international"]},
    }
    keep = dict(STRONG) | {"location": "London, England, United Kingdom"}
    drop = dict(STRONG) | {"url": "https://jobs/far", "location": "Palo Alto, CA"}
    out = pipeline.filter_by_location(src, [keep, drop])

    assert [l["url"] for l in out] == ["https://jobs/strong"]
    assert "kept 1, dropped 1" in capsys.readouterr().out


def test_location_filter_runs_inside_pipeline(monkeypatch):
    # Listings outside the configured geographies never reach scoring,
    # dedup, or the digest.
    src = {
        "name": "Geo",
        "type": "t1",
        "url": "u",
        "config": {"location_include": ["remote"]},
    }
    far = dict(STRONG) | {"url": "https://jobs/far", "location": "Memphis, TN"}
    monkeypatch.setattr(pipeline, "load_sources", lambda: [src])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [far, dict(STRONG)])

    out = pipeline.run()

    assert "https://jobs/far" not in out
    assert seen.is_seen("https://jobs/far") is False
    assert seen.is_seen("https://jobs/strong") is True


def test_dry_run_phase_order_skips_mark(monkeypatch):
    events = []
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: events.append("scrape") or [dict(STRONG)])
    monkeypatch.setattr(pipeline.matcher, "filter_and_score", lambda ls: events.append("score") or ls)
    monkeypatch.setattr(pipeline.seen, "filter_unseen", lambda ls: events.append("dedup") or ls)
    monkeypatch.setattr(
        pipeline.digest, "format_digest",
        lambda ls, highlights=None, notes="", trending=None, trending_manual=None: events.append("digest") or "DIGEST",
    )
    monkeypatch.setattr(pipeline.seen, "mark_all_seen", lambda ls: events.append("mark"))

    pipeline.run(dry_run=True)

    assert events == ["scrape", "score", "dedup", "digest"]


def test_digest_sorted_by_score_desc(monkeypatch):
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES)
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(WORTH), dict(STRONG)])

    out = pipeline.run()

    # strong (70) listed before worth (53) regardless of scrape order
    assert out.index("Staff Platform Engineer") < out.index("Senior Platform Engineer")
