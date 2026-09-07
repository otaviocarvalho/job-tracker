"""Format scored listings into a Telegram-friendly markdown digest.

Every run produces a full report: execution notes + a 90-day top-scores
highlight block on top, then NEW MATCHES when the run found any.
"""
from datetime import datetime


def _shorten(text: str, width: int) -> str:
    """Display-only truncation with an ellipsis (never mutates listing data)."""
    text = str(text)
    return text if len(text) <= width else text[: width - 3] + "..."


def merge_highlights(
    tracked: list[dict], current: list[dict], limit: int = 10
) -> list[dict]:
    """Combine DB-tracked top scores with this run's above-threshold candidates.

    `tracked` rows come from seen.top_scores() (they have first_seen);
    `current` listings are this run's scored candidates (labeled "this run").
    Dedup by URL (current wins so a fresh run shows up even if already tracked).
    """
    merged: list[dict] = []
    seen_urls: set[str] = set()
    for item in [
        {
            "title": l.get("title", "?"),
            "company": l.get("company", "?"),
            "source": l.get("source", ""),
            "score": l.get("score", 0),
            "url": l.get("url", ""),
            "first_seen": None,
        }
        for l in current
    ] + list(tracked):
        url = item.get("url") or ""
        if url and url in seen_urls:
            continue
        seen_urls.add(url)
        merged.append(item)
    merged.sort(key=lambda h: h.get("score", 0) or 0, reverse=True)
    return merged[:limit]


def format_digest(
    listings: list[dict],
    highlights: list[dict] | None = None,
    notes: str = "",
) -> str:
    """Format the full run report as markdown.

    Always contains the execution-notes line and the highlights block
    (top scores of the last 90 days), even when there are no new matches.
    NEW MATCHES (strong first, then worth a look) appears only when the
    run found new listings.
    """
    highlights = highlights or []

    strong = [l for l in listings if l.get("tier") == "strong"]
    worth = [l for l in listings if l.get("tier") == "worth"]

    lines = []
    lines.append(f"Job Tracker Digest - {datetime.now().strftime('%b %d, %H:%M')}")
    if notes:
        lines.append(notes)
    lines.append("")

    lines.append("**HIGHLIGHTS: top scores, last 90 days**")
    if highlights:
        for i, h in enumerate(highlights, 1):
            when = h.get("first_seen")
            when = when[:10] if when else "this run"
            # display-only truncation: HN "Who's Hiring" comments produce
            # run-on blobs; scoring keeps the full text shape (see AGENTS.md)
            title = _shorten(h.get("title", "?"), 120)
            company = _shorten(h.get("company", "?"), 60)
            lines.append(
                f"{i}. **{title}** at **{company}** "
                f"(Score: {h.get('score', 0)}, {when})"
            )
            if h.get("source"):
                lines.append(f"   {h['source']}")
            if h.get("url"):
                lines.append(f"   {h['url']}")
    else:
        lines.append("Nothing tracked yet.")
    lines.append("")

    if not listings:
        lines.append(
            "No new matches this run: everything above threshold was already reported."
        )
        lines.append("")
        return "\n".join(lines)

    lines.append("**NEW MATCHES**")
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
