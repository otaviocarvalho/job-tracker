"""Greenhouse job board scraper. Many VC portfolio boards use Greenhouse.

Greenhouse public API: https://boards-api.greenhouse.io/v1/boards/{board}/jobs
No auth required. Returns JSON with all job listings.
"""
import json
import urllib.request

API_BASE = "https://boards-api.greenhouse.io/v1/boards"


def scrape(board: str, source_name: str) -> list[dict]:
    """Fetch all jobs from a Greenhouse board.

    Returns list of standardized listing dicts:
        {title, company, url, location, description, source}
    """
    url = f"{API_BASE}/{board}/jobs?content=true"
    listings = []

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "job-tracker/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        for job in data.get("jobs", []):
            # Build job URL from Greenhouse board
            job_url = f"https://boards.greenhouse.io/{board}/jobs/{job.get('id', '')}"

            # Extract location from departments/locations
            location = job.get("location", {}).get("name", "") if isinstance(job.get("location"), dict) else str(job.get("location", ""))

            listings.append({
                "title": job.get("title", ""),
                "company": job.get("company_name", board),
                "url": job_url,
                "location": location,
                "description": job.get("content", "") or "",
                "source": source_name,
            })
    except Exception as e:
        print(f"  [greenhouse:{board}] Error: {e}")

    return listings
