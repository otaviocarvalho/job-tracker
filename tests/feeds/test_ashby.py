"""Ashby slice tests: SSR __appData payload extraction + error convention."""
import json
import urllib.error
import urllib.request

from conftest import urlopen_raising, urlopen_returning
from jobtracker.feeds import ashby

SOURCE = {
    "name": "ElevenLabs",
    "type": "ashby",
    "url": "https://jobs.ashbyhq.com/elevenlabs",
    "config": {"board": "elevenlabs"},
}


def _page(payload: dict) -> bytes:
    blob = json.dumps(payload).replace("</", "<\\/")
    return (
        b"<html><head><script>window.__appData = "
        + blob.encode()
        + b";</script></head><body>shell</body></html>"
    )


APP_DATA = {
    "organization": {"name": "ElevenLabs"},
    "jobBoard": {
        "teams": [
            {"id": "t1", "name": "Core Experience"},
            {"id": "t2", "name": "AI Safety"},
        ],
        "jobPostings": [
            {
                "id": "aaa-bbb",
                "title": "Full-Stack Engineer",
                "teamId": "t1",
                "locationName": "London",
                "secondaryLocations": [{"locationName": "Berlin"}],
                "workplaceType": "Remote",
            },
            {
                "id": "ccc-ddd",
                "title": "Data Scientist",
                "teamId": "t2",
                "locationName": "New York",
                "secondaryLocations": [],
                "workplaceType": "Hybrid",
            },
            {
                "id": "eee-fff",
                "title": "Ops Generalist",
                "teamId": "tX",
                "locationName": "Stockholm",
                "secondaryLocations": [],
                "workplaceType": None,
            },
        ],
    },
}


def test_scrape_parses_appdata_and_maps_listings(monkeypatch):
    seen = []

    def body_for(url):
        seen.append(url)
        return _page(APP_DATA)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_returning(body_for))
    listings = ashby.scrape(SOURCE)

    assert seen == ["https://jobs.ashbyhq.com/elevenlabs"]
    assert len(listings) == 3
    assert listings[0] == {
        "title": "Full-Stack Engineer",
        "company": "ElevenLabs",
        "url": "https://jobs.ashbyhq.com/elevenlabs/aaa-bbb",
        "location": "London / Berlin",
        "description": (
            "Full-Stack Engineer. Team: Core Experience. "
            "Workplace: Remote. Locations: London / Berlin"
        ),
        "source": "ElevenLabs",
    }
    assert listings[1]["location"] == "New York"
    assert listings[1]["description"] == (
        "Data Scientist. Team: AI Safety. Workplace: Hybrid. Locations: New York"
    )
    # unknown team and missing workplaceType degrade gracefully
    assert listings[2]["description"] == "Ops Generalist. Locations: Stockholm"


def test_scrape_company_falls_back_to_board_name(monkeypatch):
    payload = {
        "organization": {},
        "jobBoard": {
            "teams": [],
            "jobPostings": [
                {"id": "x", "title": "Platform Engineer", "locationName": "Remote"}
            ],
        },
    }

    def body_for(url):
        return _page(payload)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_returning(body_for))
    listings = ashby.scrape({**SOURCE, "config": {"board": "acme-corp"}})
    assert listings[0]["company"] == "Acme Corp"


def test_scrape_captcha_page_reports_and_returns_empty(monkeypatch, capsys):
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        urlopen_returning(lambda url: b"<html>captcha challenge</html>"),
    )
    listings = ashby.scrape(SOURCE)
    assert listings == []
    out = capsys.readouterr().out
    assert "[ashby:elevenlabs] Error:" in out


def test_scrape_network_error_reports_and_returns_empty(monkeypatch, capsys):
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        urlopen_raising(urllib.error.HTTPError(None, 401, "Unauthorized", None, None)),
    )
    listings = ashby.scrape(SOURCE)
    assert listings == []
    out = capsys.readouterr().out
    assert "[ashby:elevenlabs] Error:" in out
