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
    monkeypatch.setattr(
        pipeline, "load_groups", lambda: [{"name": "g1", "label": "G1"}]
    )
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: events.append("scrape") or [dict(STRONG)])
    monkeypatch.setattr(pipeline.matcher, "filter_and_score", lambda ls: events.append("score") or ls)
    monkeypatch.setattr(pipeline.seen, "filter_unseen", lambda ls, **kw: events.append("dedup") or ls)
    monkeypatch.setattr(
        pipeline.digest, "format_digest",
        lambda ls, highlights=None, notes="", trending=None, trending_manual=None, group_label="": events.append("digest") or "DIGEST",
    )
    monkeypatch.setattr(pipeline.seen, "mark_all_seen", lambda ls, group="": events.append("mark"))

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
        "name": "S1",
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
    monkeypatch.setattr(
        pipeline, "load_groups", lambda: [{"name": "g1", "label": "G1"}]
    )
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: events.append("scrape") or [dict(STRONG)])
    monkeypatch.setattr(pipeline.matcher, "filter_and_score", lambda ls: events.append("score") or ls)
    monkeypatch.setattr(pipeline.seen, "filter_unseen", lambda ls, **kw: events.append("dedup") or ls)
    monkeypatch.setattr(
        pipeline.digest, "format_digest",
        lambda ls, highlights=None, notes="", trending=None, trending_manual=None, group_label="": events.append("digest") or "DIGEST",
    )
    monkeypatch.setattr(pipeline.seen, "mark_all_seen", lambda ls, group="": events.append("mark"))

    pipeline.run(dry_run=True)

    assert events == ["scrape", "score", "dedup", "digest"]


def test_digest_sorted_by_score_desc(monkeypatch):
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES)
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(WORTH), dict(STRONG)])

    out = pipeline.run()

    # strong (70) listed before worth (53) regardless of scrape order
    assert out.index("Staff Platform Engineer") < out.index("Senior Platform Engineer")


def test_filter_by_group_word_boundary_gate():
    group = {"name": "emea", "require_location_keywords": ["uk", "barcelona"]}
    listings = [
        dict(STRONG) | {"url": "https://jobs/london", "location": "London, UK"},
        dict(STRONG) | {"url": "https://jobs/bcn", "location": "Barcelona, Spain"},
        dict(STRONG) | {"url": "https://jobs/ukraine", "location": "Ukraine Remote"},  # 'uk' inside a word must NOT match
        dict(STRONG) | {"url": "https://jobs/ny", "location": "New York, NY"},
        dict(STRONG) | {"url": "https://jobs/empty", "location": ""},
    ]
    out = pipeline.filter_by_group(group, listings)
    assert [l["url"] for l in out] == ["https://jobs/london", "https://jobs/bcn"]


def test_filter_by_group_without_keywords_passes_all():
    group = {"name": "global"}
    listings = [dict(STRONG), dict(WORTH)]
    assert pipeline.filter_by_group(group, listings) == listings


def test_filter_by_group_prints_drop_summary(capsys):
    group = {"name": "emea", "require_location_keywords": ["uk"]}
    pipeline.filter_by_group(group, [dict(STRONG), dict(STRONG) | {"url": "u2", "location": "London, UK"}])
    captured = capsys.readouterr().out
    assert "[emea] Group filter: kept 1, dropped 1" in captured


BARCELONA = dict(STRONG) | {
    "title": "Senior Backend Engineer",
    "url": "https://jobs/bcn",
    "location": "Barcelona, Spain",
}  # matches emea + spain-bcn gates, passes global (no gate)


def test_barcelona_listing_lands_in_all_three_groups(monkeypatch):
    """GRP-04/05: one scrape, three labeled groups, per-group dedup state."""
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(BARCELONA)])

    out = pipeline.run()

    assert "**Global**" in out and "**EMEA**" in out and "**Spain Remote + Barcelona**" in out
    assert out.count("1 above threshold | 1 new") == 3  # one labeled block per group
    assert seen.is_seen("https://jobs/bcn") is True
    assert seen.is_seen("https://jobs/bcn", group="emea") is True
    assert seen.is_seen("https://jobs/bcn", group="spain-bcn") is True


def test_global_seen_does_not_block_emea(monkeypatch):
    """GRP-02: dedup is per group - global reporting never suppresses EMEA."""
    seen.mark_seen("https://jobs/bcn", "Senior Backend Engineer")  # global only
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(BARCELONA)])

    out = pipeline.run()

    assert "Run: 1 source(s) | 1 raw | 1 above threshold | 0 new" in out  # global deduped
    assert out.count("1 above threshold | 1 new") == 2  # emea + spain still report it
    assert seen.is_seen("https://jobs/bcn", group="emea") is True


def test_remote_only_listing_is_emea_shy(monkeypatch):
    """A bare 'Remote' location cannot prove geography -> absent from gated groups."""
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(STRONG)])  # location: Remote

    out = pipeline.run()

    assert "https://jobs/strong" in out  # global (no gate)
    assert seen.is_seen("https://jobs/strong", group="emea") is False


def test_group_gate_dropped_listings_never_burn_dedup(monkeypatch):
    """Gate-dropped listings are not marked seen for the gating group (AD-0007 lineage)."""
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(STRONG)])
    pipeline.run()
    assert seen.is_seen("https://jobs/strong", group="emea") is False


def test_group_filter_selects_subset(monkeypatch):
    """GRP-07: --group picks a subset by case-insensitive substring."""
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(BARCELONA)])

    out = pipeline.run(group_filter="emea")

    assert "**EMEA**" in out
    assert "**Global**" not in out
    assert "**Spain Remote + Barcelona**" not in out
    assert seen.is_seen("https://jobs/bcn") is False  # global untouched
    assert seen.is_seen("https://jobs/bcn", group="emea") is True


def test_group_filter_no_match_returns_empty(monkeypatch, capsys):
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [])

    out = pipeline.run(group_filter="zzz")

    assert out == ""
    assert "No group matches filter: zzz" in capsys.readouterr().out


def test_group_sources_subset_narrows_pool(monkeypatch):
    """A group with a `sources` list only sees listings from those sources."""
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES)
    monkeypatch.setattr(
        pipeline,
        "load_groups",
        lambda: [{"name": "subset", "label": "S2 Only", "sources": ["S2"]}],
    )
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(STRONG)])  # source: S1

    out = pipeline.run()

    assert "**S2 Only**" in out
    assert "Run: 1 source(s) | 0 raw" in out
    assert "https://jobs/strong" not in out.split("**S2 Only**", 1)[1]
    assert seen.is_seen("https://jobs/strong", group="subset") is False


def test_trending_manual_block_only_for_flagged_groups(monkeypatch):
    TR = {
        "name": "Trendy",
        "type": "report",
        "url": "https://trendy",
        "config": {"trending": True},
    }
    monkeypatch.setattr(pipeline, "load_sources", lambda: [TR])
    monkeypatch.setattr(
        pipeline,
        "load_groups",
        lambda: [
            {"name": "g1", "label": "With Manual", "trending_manual": True},
            {"name": "g2", "label": "Without Manual"},
        ],
    )
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [])

    out = pipeline.run()

    assert out.count("TRENDING MANUAL CHECK") == 1
    manual_pos = out.index("TRENDING MANUAL CHECK")
    assert manual_pos < out.index("**Without Manual**")


def test_group_filter_is_case_insensitive_substring(monkeypatch):
    """GRP-07: the filter matches case-insensitively, like --source."""
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(BARCELONA)])

    out = pipeline.run(group_filter="EMEA")

    assert "**EMEA**" in out
    assert "**Global**" not in out


def test_dry_run_leaves_every_group_unmarked(monkeypatch):
    monkeypatch.setattr(pipeline, "load_sources", lambda: SOURCES[:1])
    monkeypatch.setattr(pipeline, "scrape_source", lambda s: [dict(BARCELONA)])

    pipeline.run(dry_run=True)

    assert seen.is_seen("https://jobs/bcn") is False
    assert seen.is_seen("https://jobs/bcn", group="emea") is False
    assert seen.is_seen("https://jobs/bcn", group="spain-bcn") is False
