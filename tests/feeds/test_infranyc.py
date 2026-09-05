"""infra.nyc slice tests: RSC chunk reassembly, bracket-matching extraction, URL fallback chain."""
import json
import urllib.error
import urllib.request

from conftest import urlopen_raising, urlopen_returning
from jobtracker.feeds import infranyc

JOB = {
    "role": "Staff Engineer",
    "company": "Acme",
    "location": "NYC",
    "seniority": "Staff",
    "stage": "Series B",
    "stack": "Go, Kafka",
    "description": "Build pipelines",
    "whyInteresting": "Huge scale",
    "roleUrl": "https://careers.example/staff",
    "careersUrl": "https://careers.example",
}


def rsc_html(payload) -> str:
    """Build a page whose RSC stream embeds payload as one __next_f chunk.

    Real RSC payloads are compact JSON (no spaces after separators) - match
    that wire format, since _extract_json_array's regex expects "key":[.
    """
    blob = json.dumps(payload, separators=(",", ":"))
    escaped = blob.replace("\\", "\\\\").replace('"', '\\"')
    return f"<script>self.__next_f.push([1,\"{escaped}\"])</script>"


def test_extract_json_array_handles_nested_brackets_and_escaped_strings():
    blob = '{"a":1,"jobs":[{"x":"[bracket \\" and ] inside"}],"b":[2,3]}'
    assert infranyc._extract_json_array(blob, "jobs") == [{"x": '[bracket " and ] inside'}]
    assert infranyc._extract_json_array('{"a":1}', "jobs") is None


def test_scrape_extracts_embedded_jobs_from_rsc_stream(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request, "urlopen", urlopen_returning(lambda url: seen.append(url) or rsc_html({"jobs": [JOB]}).encode())
    )

    listings = infranyc.scrape({"name": "infra.nyc", "type": "infranyc", "url": ""})

    assert seen == ["https://www.infra.nyc/jobs"]
    assert len(listings) == 1
    assert listings[0]["title"] == "Staff Engineer"
    assert listings[0]["company"] == "Acme"
    assert listings[0]["url"] == "https://careers.example/staff"  # roleUrl wins
    assert listings[0]["location"] == "NYC"
    assert listings[0]["source"] == "infra.nyc"
    # synthetic description joins role/seniority/stage/stack/description/whyInteresting
    assert listings[0]["description"] == "Staff Engineer Staff Series B Go, Kafka Build pipelines Huge scale"


def test_scrape_url_fallback_chain_careers_then_endpoint(monkeypatch):
    no_role_url = dict(JOB, roleUrl="")
    monkeypatch.setattr(
        urllib.request, "urlopen", urlopen_returning(lambda url: rsc_html({"jobs": [no_role_url]}).encode())
    )
    listings = infranyc.scrape({"name": "infra.nyc", "type": "infranyc", "url": ""})
    assert listings[0]["url"] == "https://careers.example"  # careersUrl second

    no_urls = dict(JOB, roleUrl="", careersUrl="")
    monkeypatch.setattr(
        urllib.request, "urlopen", urlopen_returning(lambda url: rsc_html({"jobs": [no_urls]}).encode())
    )
    listings = infranyc.scrape({"name": "infra.nyc", "type": "infranyc", "url": "https://custom.example/jobs"})
    assert listings[0]["url"] == "https://custom.example/jobs"  # endpoint last


def test_scrape_error_returns_empty_and_prints(monkeypatch, capsys):
    monkeypatch.setattr(
        urllib.request, "urlopen", urlopen_raising(urllib.error.URLError("down"))
    )
    assert infranyc.scrape({"name": "infra.nyc", "type": "infranyc"}) == []
    assert "[infranyc] Error:" in capsys.readouterr().out
