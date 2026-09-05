"""Hacker News 'Who's Hiring' feed slice.

Uses HN Algolia API to find the latest 'Ask HN: Who is hiring?' thread,
then fetches comments from that thread.
"""
import json
import re
import html
import urllib.request
import urllib.parse

from jobtracker.registry import register

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
ALGOLIA_ITEM = "https://hn.algolia.com/api/v1/items"

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    return text.strip()


def _find_whoishiring_thread() -> str | None:
    """Find the most recent 'Ask HN: Who is hiring?' thread (sorted by date)."""
    params = urllib.parse.urlencode({
        "query": "Ask HN: Who is hiring?",
        "tags": "story",
        "numericFilters": "points>50",
        "hitsPerPage": 1,
        # Sort by date descending to get the latest thread
    })
    # Use search_by_date endpoint for recency
    url = f"https://hn.algolia.com/api/v1/search_by_date?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": "job-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    hits = data.get("hits", [])
    if not hits:
        return None

    return hits[0].get("objectID")


def _fetch_comments(thread_id: str) -> list[dict]:
    """Fetch all comments from a thread."""
    url = f"{ALGOLIA_ITEM}/{thread_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "job-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())

    comments = []
    def walk(node):
        if node.get("type") == "comment":
            comments.append(node)
        for child in node.get("children", []):
            walk(child)

    walk(data)
    return comments


def _parse_hn_comment(text: str) -> dict | None:
    """Parse a HN Who's Hiring comment into a listing.

    Format is typically:
    Company Name | Location | Remote/Onsite | Title | Technologies

    We extract what we can.
    """
    text = _strip_html(text)
    if not text or len(text) < 30:
        return None

    # Skip comments that are clearly replies, not job posts
    first_line = text.split("\n")[0].strip()

    # Try to parse pipe-separated format (most common on HN)
    parts = [p.strip() for p in first_line.split("|") if p.strip()]

    company = ""
    location = ""
    title = ""
    description = text[:500]

    if len(parts) >= 2:
        company = parts[0]
        # Look for a part that looks like a job title
        for part in parts[1:]:
            part_lower = part.lower()
            if any(kw in part_lower for kw in ["engineer", "developer", "architect", "lead", "senior", "staff", "backend", "platform", "infrastructure"]):
                title = part
                break
        # Look for location
        for part in parts[1:]:
            part_lower = part.lower()
            if any(kw in part_lower for kw in ["remote", "europe", "eu", "barcelona", "berlin", "london", "amsterdam", "onsite", "hybrid", "sf", "nyc", "us", "global"]):
                location = part
                break
    else:
        # No pipes, try first line as title
        title = first_line[:120]

    # Clean up title (remove company prefix if title is too long)
    if len(title) > 120:
        title = title[:120] + "..."

    return {
        "title": title,
        "company": company,
        "url": "",
        "location": location,
        "description": description,
        "source": "HN Who's Hiring",
    }


@register("hackernews")
def scrape(source: dict) -> list[dict]:
    """Main entry: find latest thread, parse comments into listings."""
    source_name = source.get("name", "HN Who's Hiring")
    listings = []

    thread_id = _find_whoishiring_thread()
    if not thread_id:
        print("  [hackernews] Could not find Who's Hiring thread")
        return listings

    print(f"  [hackernews] Found thread: {thread_id}")

    comments = _fetch_comments(thread_id)
    print(f"  [hackernews] Fetched {len(comments)} comments")

    for comment in comments:
        text = comment.get("text", "")
        parsed = _parse_hn_comment(text)
        if parsed:
            parsed["url"] = f"https://news.ycombinator.com/item?id={comment.get('id', '')}"
            listings.append(parsed)

    return listings
