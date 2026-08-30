"""Y Combinator (Work at a Startup) job scraper.

workatastartup.com is an Inertia.js SPA. The initial HTML for /jobs embeds
the full page payload as JSON in <div id="app" data-page="...">, including
props.jobs. No public API exists (all /api/* paths 404 as of 2026-08).

List items carry only a one-liner, which is too thin for scoring. For
listings whose title contains a positive keyword (senior/staff/backend/
platform/...), we fetch the job detail page (also Inertia) and extract
descriptionHtml for the full text. Capped at MAX_DETAIL_FETCHES per run
to stay polite.

Job URL format: https://www.workatastartup.com/jobs/{id} (verified 200).
NOTE: the site returns 406 for minimal User-Agents; a full browser UA +
Accept header is required.
"""
import html as html_mod
import json
import re
import time
import urllib.request

YC_JOBS_PAGE = "https://www.workatastartup.com/jobs"
MAX_DETAIL_FETCHES = 12

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", "replace")


def _inertia_payload(page_html: str) -> dict:
    m = re.search(r'data-page="([^"]+)"', page_html)
    return json.loads(html_mod.unescape(m.group(1))) if m else {}


def _enrichment_keywords() -> list[str]:
    """Positive title keywords from criteria.yaml (single source of truth)."""
    try:
        import yaml
        from pathlib import Path
        crit_path = Path(__file__).resolve().parent.parent.parent / "config" / "criteria.yaml"
        with open(crit_path) as f:
            return list(yaml.safe_load(f).get("positive_title_keywords", {}).keys())
    except Exception:
        return ["senior", "staff", "lead", "backend", "platform", "principal"]


def scrape(url: str = "", source_name: str = "Y Combinator Jobs") -> list[dict]:
    """Fetch jobs from YC Work at a Startup via the Inertia data-page payload."""
    listings = []
    try:
        payload = _inertia_payload(_fetch(YC_JOBS_PAGE))
        jobs = payload.get("props", {}).get("jobs", [])

        base_desc = {j["id"]: " ".join(filter(None, [
            j.get("companyOneLiner", ""), j.get("roleType", ""), j.get("salary", ""),
        ])) for j in jobs}

        keywords = _enrichment_keywords()
        to_enrich = [j for j in jobs
                     if any(kw in (j.get("title", "") or "").lower() for kw in keywords)]
        to_enrich = to_enrich[:MAX_DETAIL_FETCHES]
        print(f"  [ycombinator] Enriching {len(to_enrich)}/{len(jobs)} listings with full descriptions")

        for job in jobs:
            jid = job.get("id", "")
            description = base_desc.get(jid, "")[:1000]
            if job in to_enrich:
                try:
                    detail = _inertia_payload(_fetch(f"https://www.workatastartup.com/jobs/{jid}"))
                    desc_html = detail.get("props", {}).get("job", {}).get("descriptionHtml", "")
                    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", desc_html)).strip()
                    if text:
                        description = text[:1000]
                    time.sleep(0.5)  # be polite
                except Exception as e:
                    print(f"  [ycombinator] Detail fetch failed for {jid}: {e}")

            listings.append({
                "title": job.get("title", ""),
                "company": job.get("companyName", ""),
                "url": f"https://www.workatastartup.com/jobs/{jid}",
                "location": job.get("location", ""),
                "description": description,
                "source": source_name,
            })
    except Exception as e:
        print(f"  [ycombinator] Error: {e}")

    return listings
