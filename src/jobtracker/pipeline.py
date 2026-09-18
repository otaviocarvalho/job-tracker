"""Pipeline: orchestrate scrape -> score -> dedup -> digest -> mark seen.

The run() body is the legacy main.py orchestration, kept verbatim so the
stdout contract the Hermes cron relies on does not move.
"""
import jobtracker.core.digest as digest
import jobtracker.core.scoring as matcher
import jobtracker.core.seen as seen
import jobtracker.feeds  # noqa: F401 - side effect: feed slices self-register on import
from jobtracker.core.config import load_sources
from jobtracker.registry import scrape_source


def run(reset: bool = False, source_filter: str = "", dry_run: bool = False):
    if reset:
        print("Clearing dedup database...")
        seen.clear_all()

    sources = load_sources()
    if source_filter:
        sources = [s for s in sources if source_filter.lower() in s["name"].lower()]

    # Phase 1: Scrape all sources
    print(f"\n{'='*60}")
    print(f"Scraping {len(sources)} source(s)...")
    print(f"{'='*60}")

    all_listings = []
    for source in sources:
        print(f"\n> {source['name']} ({source['type']})")
        listings = scrape_source(source)
        print(f"  Got {len(listings)} raw listings")
        all_listings.extend(listings)

    print(f"\nTotal raw listings: {len(all_listings)}")

    if not all_listings:
        print("No listings found. Done.")
        scored = []
    else:
        # Phase 2: Filter and score
        print(f"\n{'='*60}")
        print("Scoring and filtering...")
        print(f"{'='*60}")

        scored = matcher.filter_and_score(all_listings)
        print(f"After scoring: {len(scored)} listings above threshold")

        if not scored:
            print("No listings above threshold. Done.")

    # Phase 3: Dedup
    print(f"\n{'='*60}")
    print("Deduplicating...")
    print(f"{'='*60}")

    new_listings = seen.filter_unseen(scored)
    print(f"After dedup: {len(new_listings)} new listings")

    if not new_listings:
        print("No new listings. Done.")
    else:
        # Sort by score descending
        new_listings.sort(key=lambda l: l.get("score", 0), reverse=True)

    # Phase 4: Output - the report always carries execution notes and the
    # 90-day top-scores highlight, even on a run with zero new matches.
    # Sources flagged config.trending (Setter30 boards) get their own digest
    # section; report-type trending sources become the MANUAL CHECK block.
    trending_names = {
        s["name"]
        for s in sources
        if (s.get("config") or {}).get("trending")
    }
    trending_new = [l for l in new_listings if l.get("source") in trending_names]
    other_new = [l for l in new_listings if l.get("source") not in trending_names]
    trending_manual = [
        {"name": s["name"], "url": s.get("url", "")}
        for s in sources
        if s.get("type") == "report" and (s.get("config") or {}).get("trending")
    ]

    highlights = digest.merge_highlights(seen.top_scores(days=90, limit=10), scored)
    notes = (
        f"Run: {len(sources)} source(s) | {len(all_listings)} raw | "
        f"{len(scored)} above threshold | {len(new_listings)} new"
    )

    print(f"\n{'='*60}")
    print("DIGEST")
    print(f"{'='*60}\n")

    output = digest.format_digest(
        other_new,
        highlights=highlights,
        notes=notes,
        trending=trending_new,
        trending_manual=trending_manual,
    )
    print(output)

    # Mark as seen (unless dry run)
    if not dry_run and new_listings:
        seen.mark_all_seen(new_listings)
        print(f"\nMarked {len(new_listings)} listings as seen.")

    return output
