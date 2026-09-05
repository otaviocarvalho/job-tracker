"""Scoring tests derived from spec ARCH-17 and criteria.yaml values.

Expected points come from config/criteria.yaml (the spec's source of truth):
positive title (senior 15, staff 20, platform 15...), tech (kafka 15,
kubernetes 10, postgres 8...), remote +10, eu +8, cap 100, tiers 70/45.
"""
from jobtracker.core import scoring


def listing(**overrides) -> dict:
    base = {"title": "", "company": "Acme", "url": "https://x/y", "location": "", "description": "", "source": "test"}
    base.update(overrides)
    return base


def test_reject_keyword_in_title():
    rejected, reason = scoring.should_reject("Senior DevOps Engineer")
    assert rejected is True
    assert reason == "reject keyword 'devops engineer' in title"


def test_require_any_keyword_missing():
    rejected, reason = scoring.should_reject("Growth Hacker")
    assert rejected is True
    assert reason == "no required engineering keyword in title"


def test_no_reject_when_engineering_keyword_present():
    rejected, reason = scoring.should_reject("Staff Backend Engineer")
    assert rejected is False
    assert reason == ""


def test_score_title_and_tech_and_remote_bonus():
    scored = scoring.score_listing(listing(
        title="Senior Platform Engineer",
        description="Kafka, Kubernetes, Postgres",
        location="Remote",
    ))
    # title: senior 15 + platform 15; tech: kafka 15 + kubernetes 10 + postgres 8; remote +10
    assert scored["score"] == 73
    assert scored["tier"] == "strong"
    assert "title:senior" in scored["matched_signals"]
    assert "tech:kafka" in scored["matched_signals"]
    assert "remote" in scored["matched_signals"]


def test_eu_location_bonus_and_exclusivity_with_remote():
    scored = scoring.score_listing(listing(
        title="Senior Platform Engineer",
        description="Kafka",
        location="Barcelona, Spain",
    ))
    # title 30 + kafka 15 + eu +8; remote branch must not also fire
    assert scored["score"] == 53
    assert scored["tier"] == "worth"
    assert "eu-location" in scored["matched_signals"]
    assert "remote" not in scored["matched_signals"]


def test_score_capped_at_100():
    scored = scoring.score_listing(listing(
        title="Senior Staff Principal Lead Backend Platform Infrastructure Distributed Systems Engineer",
    ))
    # raw title points alone exceed 100 (135) -> capped
    assert scored["score"] == 100
    assert scored["tier"] == "strong"


def test_weak_tier_below_worth_threshold():
    scored = scoring.score_listing(listing(title="Staff Engineer"))
    # title: staff 20 only -> weak (< 45)
    assert scored["score"] == 20
    assert scored["tier"] == "weak"


def test_rejected_listing_gets_zero_and_reason():
    scored = scoring.score_listing(listing(title="Frontend Engineer"))
    assert scored["score"] == 0
    assert scored["tier"] == "rejected"
    assert "frontend" in scored["reject_reason"]


def test_filter_and_score_keeps_only_strong_and_worth():
    strong = listing(title="Senior Platform Engineer", description="Kafka", location="Remote")  # 55 -> worth? see below
    weak = listing(title="Staff Engineer")  # 20 -> weak
    rejected = listing(title="Product Manager")

    kept = scoring.filter_and_score([strong, weak, rejected])

    # strong listing: title 30 + kafka 15 + remote 10 = 55 -> worth
    assert len(kept) == 1
    assert kept[0]["tier"] == "worth"
    assert kept[0]["title"] == "Senior Platform Engineer"
