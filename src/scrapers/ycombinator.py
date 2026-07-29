"""Y Combinator job directory scraper.

Uses the YC jobs API (work at a startup) which returns JSON.
"""
import json
import urllib.request

YC_JOBS_API = "https://www.workatastartup.com/api/v1/jobs"


def scrape(url: str = "", source_name: str = "Y Combinator Jobs") -> list[dict]:
    """Fetch jobs from YC Work at a Startup."""
    listings = []

    try:
        req = urllib.request.Request(YC_JOBS_API, headers={
            "User-Agent": "job-tracker/1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        # YC API returns a list of job objects
        jobs = data if isinstance(data, list) else data.get("jobs", data.get("results", []))

        for job in jobs:
            company = job.get("startup", {}).get("name", "") if isinstance(job.get("startup"), dict) else job.get("company_name", "")
            job_url = job.get("url", f"https://www.workatastartup.com/jobs/{job.get('id', '')}")

            listings.append({
                "title": job.get("title", ""),
                "company": company,
                "url": job_url,
                "location": job.get("location", job.get("city", "")),
                "description": job.get("description", "")[:1000] if job.get("description") else "",
                "source": source_name,
            })
    except Exception as e:
        print(f"  [ycombinator] Error: {e}")
        # Fallback: try the main YC jobs page API
        try:
            alt_url = "https://www.ycombinator.com/jobs/api"
            req = urllib.request.Request(alt_url, headers={"User-Agent": "job-tracker/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            jobs = data if isinstance(data, list) else data.get("jobs", [])
            for job in jobs:
                listings.append({
                    "title": job.get("title", ""),
                    "company": job.get("startup", {}).get("name", ""),
                    "url": f"https://www.ycombinator.com/companies/{job.get('startup_id', '')}/jobs/{job.get('id', '')}",
                    "location": job.get("location", ""),
                    "description": "",
                    "source": source_name,
                })
        except Exception as e2:
            print(f"  [ycombinator] Fallback also failed: {e2}")

    return listings
