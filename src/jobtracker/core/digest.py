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
    trending: list[dict] | None = None,
    trending_manual: list[dict] | None = None,
) -> str:
    """Format the full run report as markdown.

    Always contains the execution-notes line and the highlights block
    (top scores of the last 90 days), even when there are no new matches.
    TRENDING COMPANIES (new matches from trending sources) and the MANUAL
    CHECK block render when the run has them. NEW MATCHES (strong first,
    then worth a look) covers the non-trending new listings and appears
    only when the run found any.
    """
    highlights = highlights or []
    trending = trending or []
    trending_manual = trending_manual or []

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

    if not trending and not trending_manual and not listings:
        lines.append(
            "No new matches this run: everything above threshold was already reported."
        )
        lines.append("")
        return "\n".join(lines)

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

    def render_tier_sections(items: list[dict]) -> list[str]:
        # Display-only truncation (same policy as the highlights block):
        # scoring and dedup keep the full shape, the digest shows the top
        # matches per tier so the report stays readable/deliverable.
        max_shown = 10
        out = []
        for tier, header in (("strong", "**STRONG MATCH**"), ("worth", "**WORTH A LOOK**")):
            tier_items = [l for l in items if l.get("tier") == tier]
            if not tier_items:
                continue
            out.append(header)
            out.append("")
            for i, l in enumerate(tier_items[:max_shown], 1):
                out.extend(format_listing(l, i))
            hidden = len(tier_items) - max_shown
            if hidden > 0:
                out.append(f"(+{hidden} more above threshold, not shown)")
                out.append("")
        return out

    if trending:
        lines.append("**TRENDING COMPANIES** (Setter30)")
        lines.append("")
        lines.extend(render_tier_sections(trending))

    if trending_manual:
        lines.append(
            "**TRENDING MANUAL CHECK** (no public API / captcha-gated; browse by hand)"
        )
        lines.append("")
        for m in trending_manual:
            lines.append(f"- {m.get('name', '?')}: {m.get('url', '')}")
        lines.append("")

    if listings:
        lines.append("**NEW MATCHES**")
        lines.append("")
        lines.extend(render_tier_sections(listings))
    else:
        lines.append(
            "No new non-trending matches this run: everything above threshold was already reported."
        )
        lines.append("")

    return "\n".join(lines)
