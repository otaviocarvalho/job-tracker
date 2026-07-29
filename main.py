"""Job Tracker - Main CLI entrypoint.

Usage:
    python main.py              # Full cycle: scrape -> filter -> dedup -> output
    python main.py --reset      # Clear dedup DB and run fresh
    python main.py --source X   # Run only one source by name
    python main.py --dry-run    # Scrape and score but don't mark seen
"""
import sys
import argparse
import yaml
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from scrapers import greenhouse, hackernews, ycombinator, substack
from filters import matcher
from store import seen
from output import digest


SOURCES_PATH = Path(__file__).resolve().parent / "config" / "sources.yaml"


def load_sources() -> list[dict]:
    with open(SOURCES_PATH) as f:
        data = yaml.safe_load(f)
    return data.get("sources", [])


def scrape_source(source: dict) -> list[dict]:
    """Dispatch to the right scraper based on source type."""
    stype = source.get("type", "")
    name = source.get("name", "")
    config = source.get("config", {})
    url = source.get("url", "")

    if stype == "greenhouse":
        return greenhouse.scrape(config.get("board", ""), name)
    elif stype == "hackernews":
        return hackernews.scrape(url, name)
    elif stype == "ycombinator":
        return ycombinator.scrape(url, name)
    elif stype == "substack":
        return substack.scrape(config.get("publication", ""), url, name)
    elif stype == "report":
        print(f"  [report:{name}] Report-type sources need manual review: {url}")
        return []
    else:
        print(f"  Unknown source type: {stype}")
        return []


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Tracker")
    parser.add_argument("--reset", action="store_true", help="Clear dedup DB")
    parser.add_argument("--source", type=str, default="", help="Filter by source name")
    parser.add_argument("--dry-run", action="store_true", help="Don't mark listings as seen")

    args = parser.parse_args()
    run(reset=args.reset, source_filter=args.source, dry_run=args.dry_run)
