"""Speedrun Talent Network (a16z) jobs board scraper.

Public read API: https://speedrun-talent-network.com/api/v1/jobs
No auth, no keys, free. Supports query params: fn, loc, remote, comp, q.
"""
import json
import urllib.request

API_BASE = "https://speedrun-talent-network.com/api/v1/jobs"


def scrape(url: str = "", source_name: str = "Speedrun Talent Network") -> list[dict]:
    """Fetch engineering jobs from the Speedrun Talent Network API.

    Returns list of standardized listing dicts:
        {title, company, url, location, description, source}
    """
    # Default to engineering roles; allow override via config url query params
    if url and "?" in url:
        endpoint = url
    else:
        endpoint = f"{API_BASE}?fn=engineering"

    listings = []

    try:
        req = urllib.request.Request(endpoint, headers={"User-Agent": "job-tracker/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        for job in data.get("jobs", []):
            # Build a synthetic description from structured fields for scoring
            parts = []
            parts.append(job.get("title", ""))
            parts.append(job.get("company", ""))
            parts.append(job.get("location", ""))
            parts.append(job.get("function", ""))
            if job.get("seniority"):
                parts.append(job["seniority"])
            if job.get("remote"):
                parts.append("remote")
            if job.get("comp_min") and job.get("comp_max"):
                parts.append(f"comp {job['comp_min']}-{job['comp_max']} {job.get('comp_currency', 'USD')}")
            description = " ".join(str(p) for p in parts if p)

            listings.append({
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "url": job.get("url", ""),
                "location": job.get("location", ""),
                "description": description,
                "source": source_name,
            })
    except Exception as e:
        print(f"  [speedrun] Error: {e}")

    return listings
