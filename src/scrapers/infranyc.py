"""infra.nyc jobs board scraper.

https://www.infra.nyc/jobs - curated infra/AI systems roles in NYC.
Next.js App Router site: jobs are embedded server-side in the RSC payload
(self.__next_f.push chunks in the HTML), no separate API endpoint needed.
"""
import json
import re
import urllib.request

PAGE_URL = "https://www.infra.nyc/jobs"


def _extract_json_array(blob: str, key: str):
    """Find "key":[ ... ] in an RSC blob and parse it with bracket matching."""
    m = re.search(r'"' + re.escape(key) + r'":\[', blob)
    if not m:
        return None
    i = m.end() - 1  # position of '['
    depth = 0
    in_str = False
    esc = False
    for j in range(i, len(blob)):
        ch = blob[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return json.loads(blob[i : j + 1])
    return None


def scrape(url: str = "", source_name: str = "infra.nyc") -> list[dict]:
    """Fetch the jobs page and extract the embedded jobs array.

    Returns list of standardized listing dicts:
        {title, company, url, location, description, source}
    """
    endpoint = url or PAGE_URL
    listings = []

    try:
        req = urllib.request.Request(endpoint, headers={"User-Agent": "job-tracker/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Reassemble the RSC stream from the self.__next_f.push chunks.
        # Each chunk arg is a JSON-escaped JS string; json.loads handles escapes.
        chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL)
        blob = "".join(json.loads('"' + c + '"') for c in chunks)

        jobs = _extract_json_array(blob, "jobs") or []

        for job in jobs:
            # Build a synthetic description from structured fields for scoring
            parts = [
                job.get("role", ""),
                job.get("seniority", ""),
                job.get("stage", ""),
                job.get("stack", ""),
                job.get("description", ""),
                job.get("whyInteresting", ""),
            ]
            description = " ".join(str(p) for p in parts if p)

            listings.append({
                "title": job.get("role", ""),
                "company": job.get("company", ""),
                "url": job.get("roleUrl") or job.get("careersUrl") or endpoint,
                "location": job.get("location", ""),
                "description": description,
                "source": source_name,
            })
    except Exception as e:
        print(f"  [infranyc] Error: {e}")

    return listings
