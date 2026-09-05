"""Speedrun slice tests: endpoint selection, synthetic description, error convention."""
import urllib.error
import urllib.request

from conftest import json_body, urlopen_raising, urlopen_returning
from jobtracker.feeds import speedrun

JOB = {
    "title": "Staff Engineer",
    "company": "Acme",
    "location": "Remote",
    "function": "engineering",
    "seniority": "Staff",
    "remote": True,
    "comp_min": 120,
    "comp_max": 180,
    "comp_currency": "USD",
    "url": "https://jobs.example/1",
}


def test_scrape_uses_source_url_when_it_has_query_params(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request, "urlopen", urlopen_returning(lambda url: seen.append(url) or json_body({"jobs": [JOB]}))
    )

    source = {"name": "Speedrun Talent Network", "type": "speedrun", "url": "https://speedrun.example/api/v1/jobs?fn=engineering"}
    listings = speedrun.scrape(source)

    assert seen == ["https://speedrun.example/api/v1/jobs?fn=engineering"]
    assert len(listings) == 1
    assert listings[0]["title"] == "Staff Engineer"
    assert listings[0]["company"] == "Acme"
    assert listings[0]["url"] == "https://jobs.example/1"
    assert listings[0]["source"] == "Speedrun Talent Network"
    # synthetic description joins structured fields so the matcher can score it
    assert listings[0]["description"] == "Staff Engineer Acme Remote engineering Staff remote comp 120-180 USD"


def test_scrape_defaults_to_engineering_endpoint(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request, "urlopen", urlopen_returning(lambda url: seen.append(url) or json_body({"jobs": []}))
    )

    listings = speedrun.scrape({"name": "Speedrun Talent Network", "type": "speedrun", "url": ""})

    assert seen == ["https://speedrun-talent-network.com/api/v1/jobs?fn=engineering"]
    assert listings == []


def test_scrape_error_returns_empty_and_prints(monkeypatch, capsys):
    monkeypatch.setattr(
        urllib.request, "urlopen", urlopen_raising(urllib.error.URLError("down"))
    )
    assert speedrun.scrape({"name": "Speedrun Talent Network", "type": "speedrun"}) == []
    assert "[speedrun] Error:" in capsys.readouterr().out
