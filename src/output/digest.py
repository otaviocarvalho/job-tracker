"""Format scored listings into a Telegram-friendly markdown digest."""
from datetime import datetime


def format_digest(listings: list[dict]) -> str:
    """Format listings into a markdown digest.

    Grouped by tier (strong first, then worth a look).
    Returns empty string if no listings.
    """
    if not listings:
        return ""

    strong = [l for l in listings if l.get("tier") == "strong"]
    worth = [l for l in listings if l.get("tier") == "worth"]

    lines = []
    lines.append(f"Job Tracker Digest - {datetime.now().strftime('%b %d, %H:%M')}")
    lines.append(f"{len(strong)} strong match(es), {len(worth)} worth a look")
    lines.append("")

    def format_listing(l: dict, idx: int) -> list[str]:
        parts = []
        company = l.get("company", "?")
        title = l.get("title", "?")
        score = l.get("score", 0)
        source = l.get("source", "")
        location = l.get("location", "")
        url = l.get("url", "")
        signals = l.get("matched_signals", [])

        parts.append(f"{idx}. **{title}** at **{company}** (Score: {score})")

        meta_parts = []
        if location:
            meta_parts.append(location)
        if source:
            meta_parts.append(source)
        if meta_parts:
            parts.append(f"   {', '.join(meta_parts)}")

        if url:
            parts.append(f"   {url}")

        if signals:
            # Show top 5 signals
            parts.append(f"   Signals: {', '.join(signals[:5])}")

        parts.append("")
        return parts

    if strong:
        lines.append("**STRONG MATCH**")
        lines.append("")
        for i, l in enumerate(strong, 1):
            lines.extend(format_listing(l, i))

    if worth:
        lines.append("**WORTH A LOOK**")
        lines.append("")
        for i, l in enumerate(worth, 1):
            lines.extend(format_listing(l, i))

    return "\n".join(lines)
