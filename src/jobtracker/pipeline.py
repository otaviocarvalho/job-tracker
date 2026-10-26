"""Pipeline: orchestrate scrape -> per-group (gate -> score -> dedup -> digest -> mark).

Scraping happens once per run; every search group (AD-0008) then narrows the
same raw pool through its own location gate and keeps an independent dedup
state, so one group seeing a listing never suppresses another group's report.
"""
import re

import jobtracker.core.digest as digest
import jobtracker.core.scoring as matcher
import jobtracker.core.seen as seen
import jobtracker.feeds  # noqa: F401 - side effect: feed slices self-register on import
from jobtracker.core.config import load_groups, load_sources
from jobtracker.registry import scrape_source


def filter_by_location(source: dict, listings: list[dict]) -> list[dict]:
    """Per-source location gate: config.location_include substrings (AD-0007).

    When a source entry sets `config.location_include` (list of strings),
    only listings whose `location` field contains at least one of them
    (case-insensitive) survive. Sources without the key are untouched.
    Feed-level filter on purpose: unwanted geographies never reach scoring,
    dedup, or the digest.
    """
    patterns = [
        str(p).lower()
        for p in ((source.get("config") or {}).get("location_include") or [])
    ]
    if not patterns:
        return listings
    kept = [
        l
        for l in listings
        if any(p in str(l.get("location") or "").lower() for p in patterns)
    ]
    dropped = len(listings) - len(kept)
    if dropped:
        print(
            f"  Location filter ({source.get('name', '?')}): "
            f"kept {len(kept)}, dropped {dropped} outside {patterns}"
        )
    return kept


def filter_by_group(group: dict, listings: list[dict]) -> list[dict]:
    """Group-level location gate: require_location_keywords as word boundaries (AD-0008).

    Matches the group's `require_location_keywords` against the `location`
    field only (same field the AD-0007 per-source gate reads). Word-boundary
    matching so `uk` hits "London, UK" but not "Ukraine". A listing with an
    empty location cannot prove geography and is dropped for gated groups;
    groups without keywords pass everything through untouched.
    """
    keywords = group.get("require_location_keywords") or []
    if not keywords:
        return listings
    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")\b"
    )
    kept = [
        l for l in listings if pattern.search(str(l.get("location") or "").lower())
    ]
    dropped = len(listings) - len(kept)
    if dropped:
        print(
            f"  [{group['name']}] Group filter: kept {len(kept)}, "
            f"dropped {dropped} (require-location gate)"
        )
    return kept


def run(
    reset: bool = False,
    source_filter: str = "",
    dry_run: bool = False,
    group_filter: str = "",
):
    if reset:
        print("Clearing dedup database...")
        seen.clear_all()

    sources = load_sources()
    if source_filter:
        sources = [s for s in sources if source_filter.lower() in s["name"].lower()]

    groups = load_groups()
    if group_filter:
        groups = [
            g for g in groups if group_filter.lower() in g["name"].lower()
        ]
        if not groups:
            print(f"No group matches filter: {group_filter}")
            return ""

    # Phase 1: Scrape all sources once; groups fan out over the same pool
    print(f"\n{'='*60}")
    print(f"Scraping {len(sources)} source(s)...")
    print(f"{'='*60}")

    all_listings = []
    for source in sources:
        print(f"\n> {source['name']} ({source['type']})")
        listings = scrape_source(source)
        print(f"  Got {len(listings)} raw listings")
        listings = filter_by_location(source, listings)
        all_listings.extend(listings)

    print(f"\nTotal raw listings: {len(all_listings)}")

    if not all_listings:
        print("No listings found. Done.")

    # Phases 2-4 per group: gate -> score -> dedup -> digest block.
    # Each group keeps its own dedup state, so the same listing can be new
    # in EMEA while already reported globally (AD-0008).
    blocks = []
    to_mark = []  # (group_name, new_listings)
    for group in groups:
        name = group["name"]
        src_names = (
            set(group["sources"])
            if group.get("sources")
            else {s["name"] for s in sources}
        )
        group_sources = [s for s in sources if s["name"] in src_names]
        raw = [l for l in all_listings if l.get("source") in src_names]
        raw = filter_by_group(group, raw)

        scored = matcher.filter_and_score(raw) if raw else []
        new_listings = seen.filter_unseen(scored, group=name)
        if new_listings:
            new_listings.sort(key=lambda l: l.get("score", 0), reverse=True)
        print(f"  [{name}] {len(scored)} above threshold | {len(new_listings)} new")
        if not new_listings:
            print(f"  [{name}] No new listings. Done.")

        # Sources flagged config.trending (Setter30 boards) get their own
        # digest section; report-type trending sources become the MANUAL
        # CHECK block, rendered only for groups that ask for it.
        trending_names = {
            s["name"]
            for s in group_sources
            if (s.get("config") or {}).get("trending")
        }
        trending_new = [l for l in new_listings if l.get("source") in trending_names]
        other_new = [
            l for l in new_listings if l.get("source") not in trending_names
        ]
        trending_manual = (
            [
                {"name": s["name"], "url": s.get("url", "")}
                for s in group_sources
                if s.get("type") == "report" and (s.get("config") or {}).get("trending")
            ]
            if group.get("trending_manual")
            else []
        )

        highlights = digest.merge_highlights(
            seen.top_scores(days=90, limit=10, group=name), scored
        )
        notes = (
            f"Run: {len(group_sources)} source(s) | {len(raw)} raw | "
            f"{len(scored)} above threshold | {len(new_listings)} new"
        )
        blocks.append(
            digest.format_digest(
                other_new,
                highlights=highlights,
                notes=notes,
                trending=trending_new,
                trending_manual=trending_manual,
                group_label=group["label"],
            )
        )
        to_mark.append((name, new_listings))

    # Phase 4: Output - one DIGEST header, one labeled block per group. The
    # report always carries execution notes and the 90-day top-scores
    # highlight per group, even on a run with zero new matches.
    print(f"\n{'='*60}")
    print("DIGEST")
    print(f"{'='*60}\n")

    output = "\n\n".join(blocks)
    print(output)

    # Mark as seen, per group (unless dry run)
    if not dry_run:
        for name, new_listings in to_mark:
            if new_listings:
                seen.mark_all_seen(new_listings, group=name)
                print(f"\nMarked {len(new_listings)} listings as seen ({name}).")

    return output
