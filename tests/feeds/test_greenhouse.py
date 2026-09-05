"""Greenhouse slice tests: JSON API mapping (dict and str locations) + error convention."""
import urllib.error
import urllib.request

from conftest import json_body, urlopen_raising, urlopen_returning
from jobtracker.feeds import greenhouse

SOURCE = {
    "name": "a16z Portfolio",
    "type": "greenhouse",
    "url": "https://portfolio-jobs.a16z.com",
    "config": {"board": "a16z"},
}

JOBS_PAYLOAD = {
    "jobs": [
        {
            "id": "111",
            "title": "Senior Backend Engineer",
            "company_name": "Acme",
            "location": {"name": "Barcelona"},
            "content": "<p>Go</p>",
        },
        {
            "id": "222",
            "title": "Platform Engineer",
            "location": "Remote",
        },
    ]
}


def test_scrape_fetches_board_api_and_maps_listings(monkeypatch):
    seen = []

    def body_for(url):
        seen.append(url)
        return json_body(JOBS_PAYLOAD)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_returning(body_for))
    listings = greenhouse.scrape(SOURCE)

    assert seen == ["https://boards-api.greenhouse.io/v1/boards/a16z/jobs?content=true"]
    assert len(listings) == 2
    assert listings[0] == {
        "title": "Senior Backend Engineer",
        "company": "Acme",
        "url": "https://boards.greenhouse.io/a16z/jobs/111",
        "location": "Barcelona",
        "description": "<p>Go</p>",
        "source": "a16z Portfolio",
    }
    # str location branch
    assert listings[1]["location"] == "Remote"
    # company falls back to the board slug when company_name is absent
    assert listings[1]["company"] == "a16z"
    assert listings[1]["url"] == "https://boards.greenhouse.io/a16z/jobs/222"


def test_scrape_error_returns_empty_and_prints(monkeypatch, capsys):
    monkeypatch.setattr(
        urllib.request, "urlopen", urlopen_raising(urllib.error.URLError("down"))
    )
    assert greenhouse.scrape(SOURCE) == []
    assert "[greenhouse:a16z] Error:" in capsys.readouterr().out
