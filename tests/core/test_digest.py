"""Digest formatter tests (ARCH-19).

format_digest is the full run report: execution notes + 90-day highlights on
top, NEW MATCHES section only when the run found new listings.
"""
from jobtracker.core import digest


def l(idx, tier, score, signals=None, location="", url="https://jobs/x"):
    return {
        "title": f"Role {idx}",
        "company": f"Company {idx}",
        "score": score,
        "tier": tier,
        "matched_signals": signals or [],
        "location": location,
        "source": "Test Source",
        "url": url,
    }


def h(idx, score, first_seen="2026-09-01 10:00:00", url=None):
    return {
        "title": f"Highlight {idx}",
        "company": f"Company {idx}",
        "score": score,
        "source": "Test Source",
        "url": url or f"https://jobs/h/{idx}",
        "first_seen": first_seen,
    }


def test_empty_input_still_renders_the_report_shell():
    out = digest.format_digest([])
    assert out != ""
    assert "No new matches this run" in out
    assert "**HIGHLIGHTS: top scores, last 90 days**" in out


def test_header_carries_notes_line():
    out = digest.format_digest([], notes="Run: 2 source(s) | 10 raw | 3 above threshold | 0 new")
    lines = out.splitlines()
    assert lines[0].startswith("Job Tracker Digest - ")
    assert lines[1] == "Run: 2 source(s) | 10 raw | 3 above threshold | 0 new"


def test_highlights_render_on_top_with_score_and_date():
    out = digest.format_digest([l(1, "strong", 80)], highlights=[h(1, 92)])
    assert out.index("**HIGHLIGHTS: top scores, last 90 days**") < out.index("**NEW MATCHES**")
    assert "1. **Highlight 1** at **Company 1** (Score: 92, 2026-09-01)" in out
    assert "   https://jobs/h/1" in out


def test_highlight_without_first_seen_is_labeled_this_run():
    out = digest.format_digest([], highlights=[h(1, 70, first_seen=None)])
    assert "(Score: 70, this run)" in out


def test_empty_highlights_renders_placeholder():
    out = digest.format_digest([])
    assert "Nothing tracked yet." in out


def test_no_tier_sections_when_only_other_tiers():
    out = digest.format_digest([l(1, "weak", 10)])
    assert "**STRONG MATCH**" not in out
    assert "**WORTH A LOOK**" not in out
    assert "**NEW MATCHES**" in out


def test_strong_section_before_worth_section():
    out = digest.format_digest([l(1, "worth", 50), l(2, "strong", 80)])
    assert out.index("**STRONG MATCH**") < out.index("**WORTH A LOOK**")


def test_listing_block_contains_title_company_score_url_and_meta():
    out = digest.format_digest([l(1, "strong", 80, location="Remote")])
    assert "1. **Role 1** at **Company 1** (Score: 80)" in out
    assert "   Remote, Test Source" in out
    assert "   https://jobs/x" in out


def test_signals_truncated_to_five():
    signals = [f"s{i}" for i in range(7)]
    out = digest.format_digest([l(1, "strong", 90, signals=signals)])
    assert "Signals: s0, s1, s2, s3, s4" in out
    assert "s5" not in out
    assert "s6" not in out


def test_merge_highlights_sorts_by_score_and_dedups_by_url():
    tracked = [h(1, 60), h(2, 90, url="https://jobs/dup")]
    current = [
        {"title": "Fresh", "company": "C", "source": "s", "score": 75, "url": "https://jobs/dup", "tier": "strong"},
        {"title": "Mid", "company": "C", "source": "s", "score": 80, "url": "https://jobs/mid", "tier": "strong"},
    ]
    merged = digest.merge_highlights(tracked, current, limit=10)
    scores = [m["score"] for m in merged]
    assert scores == sorted(scores, reverse=True)
    # current entry wins over the tracked row with the same URL
    assert [m["title"] for m in merged if m["url"] == "https://jobs/dup"] == ["Fresh"]
    assert len(merged) == 3


def test_merge_highlights_respects_limit():
    tracked = [h(i, score=100 - i) for i in range(15)]
    merged = digest.merge_highlights(tracked, [], limit=10)
    assert len(merged) == 10
    assert merged[0]["score"] == 100
