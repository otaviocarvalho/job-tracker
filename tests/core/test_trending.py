"""Trending digest sections (AD-0006): TRENDING COMPANIES + MANUAL CHECK.

format_digest splits new listings into trending (Setter30 sources flagged
config.trending) and the rest; report-type trending sources render a static
manual-check block. The plain no-args path stays byte-identical to the
pre-trending output (cron golden contract).
"""
from jobtracker.core import digest


def l(idx, tier, score, source="Test Source"):
    return {
        "title": f"Role {idx}",
        "company": f"Company {idx}",
        "score": score,
        "tier": tier,
        "matched_signals": [],
        "location": "Remote",
        "source": source,
        "url": f"https://jobs/t/{idx}",
    }


def c(idx, tier, score, company):
    """Listing with an explicit company (source stays neutral so assertions
    can count exactly one occurrence per shown listing)."""
    item = l(idx, tier, score)
    item["company"] = company
    return item


def test_trending_section_groups_by_tier_before_new_matches():
    trending = [l(1, "strong", 90, "Anthropic"), l(2, "worth", 50, "Anthropic")]
    other = [l(3, "strong", 80, "HN Who's Hiring")]
    out = digest.format_digest(other, trending=trending)

    assert "**TRENDING COMPANIES** (Setter30)" in out
    assert "**NEW MATCHES**" in out
    assert out.index("**TRENDING COMPANIES**") < out.index("**NEW MATCHES**")
    assert out.index("**STRONG MATCH**") < out.index("**WORTH A LOOK**")
    # trending listings do not repeat under NEW MATCHES
    assert out.count("Role 1") == 1
    assert out.count("Role 3") == 1


def test_manual_check_block_lists_sources_with_urls():
    manual = [
        {"name": "Anysphere (Cursor)", "url": "https://cursor.com/careers"},
        {"name": "Kraken", "url": "https://jobs.kraken.com"},
    ]
    out = digest.format_digest([], trending_manual=manual)

    assert "**TRENDING MANUAL CHECK**" in out
    assert "- Anysphere (Cursor): https://cursor.com/careers" in out
    assert "- Kraken: https://jobs.kraken.com" in out
    assert "No new non-trending matches this run" in out


def test_plain_no_trending_path_is_unchanged():
    out = digest.format_digest([])
    assert "TRENDING" not in out
    assert "No new matches this run: everything above threshold was already reported." in out


def test_only_trending_new_skips_empty_new_matches_header():
    trending = [l(1, "strong", 95, "OpenAI")]
    out = digest.format_digest([], trending=trending)
    assert "**TRENDING COMPANIES** (Setter30)" in out
    assert "**NEW MATCHES**" not in out
    assert "No new non-trending matches this run" in out


def test_tier_display_capped_with_hidden_footer():
    many = [l(i, "strong", 90 - i, "Databricks") for i in range(15)]
    out = digest.format_digest([], trending=many)
    assert out.count("Databricks") == 10  # max 10 shown per tier (source meta)
    assert "(+5 more above threshold, not shown)" in out


def test_per_company_cap_keeps_other_employers_visible():
    # 5 Anthropic roles would fill a whole 10-slot tier; the cap reserves
    # room for the other company even when Anthropic out-scores everything.
    flood = [c(i, "strong", 90 - i, "Anthropic") for i in range(5)]
    other = [c(50, "strong", 40, "Databricks")]
    out = digest.format_digest([], trending=flood + other)
    assert out.count("Anthropic") == 3
    assert out.count("Databricks") == 1
    assert "(+2 more above threshold, not shown)" in out


def test_per_company_cap_is_per_tier_and_configurable():
    # Same employer in both tiers: each tier gets its own allowance.
    items = [c(i, "strong", 90 - i, "Anthropic") for i in range(4)]
    items += [c(i, "worth", 50 - i, "Anthropic") for i in range(4)]
    out = digest.format_digest([], trending=items, max_per_company=2)
    assert out.count("Anthropic") == 4  # 2 strong + 2 worth
    assert "(+2 more above threshold, not shown)" in out


def test_per_company_cap_applies_to_new_matches_section_too():
    flood = [c(i, "strong", 90 - i, "Anthropic") for i in range(5)]
    out = digest.format_digest(flood)
    assert out.count("Anthropic") == 3
    assert "(+2 more above threshold, not shown)" in out


def test_cap_per_company_is_case_insensitive_and_zero_disables():
    items = [
        {"company": c, "title": "t", "url": f"u{i}"}
        for i, c in enumerate(["acme", "Acme", "ACME", "acme ", "Other"])
    ]
    assert len(digest.cap_per_company(items, 2)) == 3  # 2x acme + Other
    assert len(digest.cap_per_company(items, 0)) == 5  # 0 = disabled
