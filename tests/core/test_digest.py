"""Digest formatter tests (ARCH-19)."""
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


def test_empty_input_renders_empty_string():
    assert digest.format_digest([]) == ""


def test_digest_header_and_counts():
    out = digest.format_digest([l(1, "strong", 80), l(2, "worth", 50)])
    lines = out.splitlines()
    assert lines[0].startswith("Job Tracker Digest - ")
    assert lines[1] == "1 strong match(es), 1 worth a look"


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


def test_no_tier_sections_when_only_other_tiers():
    # feed of only weak/rejected tiers renders headers with zero counts but no listing blocks
    out = digest.format_digest([l(1, "weak", 10)])
    assert "**STRONG MATCH**" not in out
    assert "**WORTH A LOOK**" not in out
    assert "0 strong match(es), 0 worth a look" in out
