"""Substack RSS feed scraper.

Fetches RSS feed from {publication}.substack.com/feed and extracts
job-related posts.
"""
import urllib.request
import re
from xml.etree import ElementTree as ET


def scrape(publication: str = "", url: str = "", source_name: str = "") -> list[dict]:
    """Fetch Substack RSS feed and return posts as listings."""
    if publication:
        feed_url = f"https://{publication}.substack.com/feed"
    elif url:
        feed_url = f"{url.rstrip('/')}/feed"
    else:
        print(f"  [substack] No publication or URL provided for {source_name}")
        return []

    listings = []

    try:
        req = urllib.request.Request(feed_url, headers={"User-Agent": "job-tracker/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read().decode()

        root = ET.fromstring(xml_data)

        # RSS 2.0 format: channel/item
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            description = item.findtext("description", "")

            if not title:
                continue

            # Substack newsletters are posts, not individual jobs.
            # We list them as "digest" entries for Otavio to browse.
            listings.append({
                "title": f"[Newsletter] {title}",
                "company": source_name or publication,
                "url": link,
                "location": "",
                "description": re.sub(r"<[^>]+>", "", description)[:500],
                "source": source_name or publication,
            })
    except Exception as e:
        print(f"  [substack:{publication}] Error: {e}")

    return listings
