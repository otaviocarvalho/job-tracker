"""Score job listings against profile criteria."""
from .config import load_criteria

_criteria = None


def _get_criteria():
    global _criteria
    if _criteria is None:
        _criteria = load_criteria()
    return _criteria


def _normalize(text: str) -> str:
    return (text or "").lower()


def should_reject(title: str, description: str = "") -> tuple[bool, str]:
    """Check hard reject conditions. Returns (rejected, reason)."""
    c = _get_criteria()
    title_l = _normalize(title)
    desc_l = _normalize(description)

    # Check reject keywords in title
    for kw in c.get("reject_title_keywords", []):
        if kw in title_l:
            return True, f"reject keyword '{kw}' in title"

    # Check at least one required keyword present
    require_any = c.get("require_any_title_keyword", [])
    if require_any:
        has_any = any(kw in title_l for kw in require_any)
        if not has_any:
            return True, "no required engineering keyword in title"

    return False, ""


def score_listing(listing: dict) -> dict:
    """Score a single listing. Adds 'score', 'tier', and 'reject_reason' fields."""
    title = listing.get("title", "")
    description = listing.get("description", "")
    location = _normalize(listing.get("location", ""))
    full_text = f"{title} {description}".lower()

    # Hard reject check
    rejected, reason = should_reject(title, description)
    if rejected:
        listing["score"] = 0
        listing["tier"] = "rejected"
        listing["reject_reason"] = reason
        return listing

    c = _get_criteria()
    score = 0
    matched = []

    # Positive title keywords
    for kw, points in c.get("positive_title_keywords", {}).items():
        if kw in _normalize(title):
            score += points
            matched.append(f"title:{kw}")

    # Positive tech keywords
    for kw, points in c.get("positive_tech_keywords", {}).items():
        if kw in full_text:
            score += points
            matched.append(f"tech:{kw}")

    # Positive domain keywords
    for kw, points in c.get("positive_domain_keywords", {}).items():
        if kw in full_text:
            score += points
            matched.append(f"domain:{kw}")

    # Location bonus
    remote_kws = c.get("remote_keywords", [])
    eu_locs = c.get("eu_locations", [])

    if any(kw in location or kw in full_text for kw in remote_kws):
        score += 10
        matched.append("remote")
    elif any(loc in location or loc in full_text for loc in eu_locs):
        score += 8
        matched.append("eu-location")

    # Cap at 100
    score = min(score, 100)

    # Determine tier
    strong = c.get("strong_match_threshold", 70)
    worth = c.get("worth_a_look_threshold", 45)

    if score >= strong:
        tier = "strong"
    elif score >= worth:
        tier = "worth"
    else:
        tier = "weak"

    listing["score"] = score
    listing["tier"] = tier
    listing["matched_signals"] = matched
    listing["reject_reason"] = ""
    return listing


def filter_and_score(listings: list[dict]) -> list[dict]:
    """Score all listings and return only those above the worth-a-look threshold."""
    c = _get_criteria()
    worth_threshold = c.get("worth_a_look_threshold", 45)

    scored = [score_listing(l) for l in listings]
    return [l for l in scored if l["tier"] in ("strong", "worth")]
