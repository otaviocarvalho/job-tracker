"""Lever job board feed slice.

Lever public postings API: https://api.lever.co/v0/postings/{board}?mode=json
No auth required. Returns a JSON array of posting dicts.
"""
import json
import urllib.request

from jobtracker.registry import register

API_BASE = "https://api.lever.co/v0/postings"


@register("lever")
def scrape(source: dict) -> list[dict]:
    """Fetch all jobs from a Lever board.

    Returns list of standardized listing dicts:
        {title, company, url, location, description, source}
    """
    board = source.get("config", {}).get("board", "")
    source_name = source.get("name", "")
    url = f"{API_BASE}/{board}?mode=json"
    listings = []

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "job-tracker/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        for job in data:
            cats = job.get("categories") or {}
            listings.append({
                "title": job.get("text", ""),
                "company": source_name,
                "url": job.get("hostedUrl", ""),
                "location": cats.get("location", ""),
                "description": job.get("descriptionPlain", "") or "",
                "source": source_name,
            })
    except Exception as e:
        print(f"  [lever:{board}] Error: {e}")

    return listings
