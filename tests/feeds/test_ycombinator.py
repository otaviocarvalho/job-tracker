"""Y Combinator slice tests: Inertia payload extraction, enrichment gating, fallback keywords."""
import html as html_mod
import json
import urllib.request
from types import SimpleNamespace

from conftest import urlopen_returning
from jobtracker.feeds import ycombinator as yc

JOBS = [
    {
        "id": "j1",
        "title": "Staff Backend Engineer",
        "companyName": "Acme",
        "location": "Remote",
        "companyOneLiner": "Payments infra",
        "roleType": "Full-time",
        "salary": "$150k",
    },
    {
        "id": "j2",
        "title": "Product Designer",
        "companyName": "Beta",
        "location": "SF",
        "companyOneLiner": "Design tooling",
        "roleType": "Full-time",
        "salary": "",
    },
]


def inertia_html(payload) -> str:
    escaped = html_mod.escape(json.dumps(payload), quote=True)
    return f'<div id="app" data-page="{escaped}"></div>'


def list_page_body() -> bytes:
    return inertia_html({"props": {"jobs": JOBS}}).encode()


def detail_body() -> bytes:
    return inertia_html({"props": {"job": {"descriptionHtml": "<p>Go and Kafka systems</p>"}}}).encode()


def test_inertia_payload_extracts_props():
    payload = yc._inertia_payload(inertia_html({"props": {"jobs": [1, 2]}}))
    assert payload == {"props": {"jobs": [1, 2]}}


def test_inertia_payload_without_data_page_returns_empty():
    assert yc._inertia_payload("<html><body>shell</body></html>") == {}


def test_scrape_enriches_only_keyword_matching_titles(monkeypatch):
    monkeypatch.setattr(yc, "load_criteria", lambda: {"positive_title_keywords": {"staff": 20}})
    monkeypatch.setattr("time.sleep", lambda s: None)  # no politeness delay in tests

    fetched = []

    def body_for(url):
        fetched.append(url)
        return list_page_body() if url == yc.YC_JOBS_PAGE else detail_body()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_returning(body_for))

    listings = yc.scrape({"name": "Y Combinator Jobs", "type": "ycombinator"})

    assert len(listings) == 2
    staff = next(l for l in listings if l["title"] == "Staff Backend Engineer")
    designer = next(l for l in listings if l["title"] == "Product Designer")

    # enriched listing: descriptionHtml stripped of tags
    assert staff["description"] == "Go and Kafka systems"
    assert staff["url"] == "https://www.workatastartup.com/jobs/j1"
    assert staff["source"] == "Y Combinator Jobs"
    # non-matching title keeps the one-liner join, no detail fetch
    assert designer["description"] == "Design tooling Full-time"
    assert "https://www.workatastartup.com/jobs/j1" in fetched
    assert "https://www.workatastartup.com/jobs/j2" not in fetched


def test_enrichment_keywords_come_from_shared_criteria_loader(monkeypatch):
    monkeypatch.setattr(
        yc, "load_criteria", lambda: {"positive_title_keywords": {"zzz": 5, "aaa": 3}}
    )
    assert yc._enrichment_keywords() == ["zzz", "aaa"]


def test_enrichment_keywords_fallback_when_criteria_unavailable(monkeypatch):
    def boom():
        raise RuntimeError("no config")

    monkeypatch.setattr(yc, "load_criteria", boom)
    assert yc._enrichment_keywords() == [
        "senior", "staff", "lead", "backend", "platform", "principal",
    ]
