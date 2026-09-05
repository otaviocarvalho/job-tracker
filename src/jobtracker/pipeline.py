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
        return

    # Phase 2: Filter and score
    print(f"\n{'='*60}")
    print("Scoring and filtering...")
    print(f"{'='*60}")

    scored = matcher.filter_and_score(all_listings)
    print(f"After scoring: {len(scored)} listings above threshold")

    if not scored:
        print("No listings above threshold. Done.")
        return

    # Phase 3: Dedup
    print(f"\n{'='*60}")
    print("Deduplicating...")
    print(f"{'='*60}")

    new_listings = seen.filter_unseen(scored)
    print(f"After dedup: {len(new_listings)} new listings")

    if not new_listings:
        print("No new listings. Done.")
        return

    # Sort by score descending
    new_listings.sort(key=lambda l: l.get("score", 0), reverse=True)

    # Phase 4: Output
    print(f"\n{'='*60}")
    print("DIGEST")
    print(f"{'='*60}\n")

    output = digest.format_digest(new_listings)
    print(output)

    # Mark as seen (unless dry run)
    if not dry_run:
        seen.mark_all_seen(new_listings)
        print(f"\nMarked {len(new_listings)} listings as seen.")

    return output
