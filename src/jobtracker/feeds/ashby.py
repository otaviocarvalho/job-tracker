"""Ashby job board feed slice (Setter30 trending companies).

Ashby hosts boards at https://jobs.ashbyhq.com/{board}. The public posting
API (api.ashbyhq.com/posting-api/job-list/{board}) returns 401 for most
boards, but the board page itself is server-rendered with the full job list
embedded in an inline `window.__appData = {...}` JSON blob. Same policy as
infra.nyc / YC: parse the embedded data, never the rendered shell.

A plain urllib request (no cookies) gets the SSR page; the browser CAPTCHA
that blocks headless visitors does not apply to this endpoint.
"""
import json
import urllib.request

from jobtracker.registry import register

BOARD_BASE = "https://jobs.ashbyhq.com/{board}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

_WORKPLACE_LABELS = {
    "remote": "Remote",
    "hybrid": "Hybrid",
    "onsite": "On-site",
}


def _extract_app_data(html: str) -> dict:
    """Pull the `window.__appData = {...}` JSON object out of the SSR page."""
    marker = html.find("window.__appData")
    if marker < 0:
        raise ValueError("no window.__appData payload (captcha page or shell HTML)")
    start = html.find("{", marker)
    if start < 0:
        raise ValueError("__appData marker found but no JSON object follows")
    obj, _ = json.JSONDecoder().raw_decode(html[start:])
    if not isinstance(obj, dict):
        raise ValueError("__appData is not a JSON object")
    return obj


def _format_location(posting: dict) -> str:
    """Primary location plus secondary locations, e.g. 'Stockholm / London'."""
    parts = [posting.get("locationName") or ""]
    parts += [
        s.get("locationName") or "" for s in posting.get("secondaryLocations") or []
    ]
    return " / ".join(p for p in parts if p)


def _company_name(app_data: dict, board: str) -> str:
    org = app_data.get("organization") or {}
    return org.get("name") or board.replace("-", " ").title()


@register("ashby")
def scrape(source: dict) -> list[dict]:
    """Fetch all jobs from an Ashby board via the SSR __appData payload.

    Returns list of standardized listing dicts:
        {title, company, url, location, description, source}
    """
    board = source.get("config", {}).get("board", "")
    source_name = source.get("name", "")
    url = BOARD_BASE.format(board=board)
    listings = []

    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", "ignore")

        app_data = _extract_app_data(html)
        company = _company_name(app_data, board)
        job_board = app_data.get("jobBoard") or {}
        teams = {
            t.get("id"): (t.get("name") or "")
            for t in job_board.get("teams") or []
        }

        for posting in job_board.get("jobPostings") or []:
            job_id = posting.get("id", "")
            title = posting.get("title", "")
            location = _format_location(posting)
            workplace = _WORKPLACE_LABELS.get(
                str(posting.get("workplaceType") or "").lower(), ""
            )
            team = teams.get(posting.get("teamId"), "")
            comp = posting.get("compensationTierSummary") or ""

            # Synthetic description: Ashby SSR omits the full job body, so
            # give the keyword matcher whatever structured fields exist.
            description = ". ".join(
                p
                for p in [
                    title,
                    f"Team: {team}" if team else "",
                    f"Workplace: {workplace}" if workplace else "",
                    f"Locations: {location}" if location else "",
                    f"Compensation: {comp}" if comp else "",
                ]
                if p
            )

            listings.append({
                "title": title,
                "company": company,
                "url": f"{BOARD_BASE.format(board=board)}/{job_id}",
                "location": location,
                "description": description,
                "source": source_name,
            })
    except Exception as e:
        print(f"  [ashby:{board}] Error: {e}")

    return listings
