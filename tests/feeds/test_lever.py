"""Lever slice tests: postings API mapping + error convention."""
import urllib.error
import urllib.request

from conftest import json_body, urlopen_raising, urlopen_returning
from jobtracker.feeds import lever

SOURCE = {
    "name": "Spotify",
    "type": "lever",
    "url": "https://jobs.lever.co/spotify",
    "config": {"board": "spotify"},
}

JOBS_PAYLOAD = [
    {
        "id": "abc-1",
        "text": "Senior Backend Engineer",
        "hostedUrl": "https://jobs.lever.co/spotify/abc-1",
        "categories": {"location": "Madrid, Spain", "team": "Engineering"},
        "descriptionPlain": "Go and Python.",
    },
    {
        "id": "abc-2",
        "text": "Platform Engineer",
        "hostedUrl": "https://jobs.lever.co/spotify/abc-2",
        "categories": {},
    },
]


def test_scrape_fetches_postings_api_and_maps_listings(monkeypatch):
    seen = []

    def body_for(url):
        seen.append(url)
        return json_body(JOBS_PAYLOAD)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_returning(body_for))
    listings = lever.scrape(SOURCE)

    assert seen == ["https://api.lever.co/v0/postings/spotify?mode=json"]
    assert len(listings) == 2
    assert listings[0] == {
        "title": "Senior Backend Engineer",
        "company": "Spotify",
        "url": "https://jobs.lever.co/spotify/abc-1",
        "location": "Madrid, Spain",
        "description": "Go and Python.",
        "source": "Spotify",
    }
    assert listings[1]["location"] == ""
    assert listings[1]["description"] == ""


def test_scrape_never_raises_on_http_error(monkeypatch, capsys):
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        urlopen_raising(urllib.error.HTTPError("u", 404, "Not Found", None, None)),
    )
    listings = lever.scrape(SOURCE)

    assert listings == []
    assert "[lever:spotify] Error:" in capsys.readouterr().out
