"""Hacker News slice tests: comment parsing (pure) + flow with mocked Algolia calls."""
import urllib.request

from conftest import urlopen_returning
from jobtracker.feeds import hackernews


def test_strip_html_unescapes_entities():
    assert hackernews._strip_html("<p>Go &amp; Kafka</p>") == "Go & Kafka"


def test_parse_pipe_comment_extracts_company_title_location():
    text = "Acme Corp | Remote (EU) | Senior Backend Engineer | Go, Kafka, AWS " + "detail " * 20
    parsed = hackernews._parse_hn_comment(text)

    assert parsed["company"] == "Acme Corp"
    assert parsed["title"] == "Senior Backend Engineer"
    assert parsed["location"] == "Remote (EU)"
    assert parsed["source"] == "HN Who's Hiring"
    # description is the cleaned (tag-stripped, unescaped, trimmed) comment text
    assert parsed["description"] == text.strip()[:500]
    assert parsed["url"] == ""  # flow assigns the item URL later


def test_parse_comment_without_pipes_uses_first_line_as_title():
    text = "We are hiring a Staff Infrastructure Engineer to join our platform team" + " x" * 20
    parsed = hackernews._parse_hn_comment(text)

    assert parsed["title"].startswith("We are hiring a Staff Infrastructure Engineer")
    assert parsed["company"] == ""


def test_parse_short_comment_returns_none():
    assert hackernews._parse_hn_comment("hire me") is None
    assert hackernews._parse_hn_comment("") is None


def test_scrape_flow_finds_thread_and_builds_item_urls(monkeypatch):
    monkeypatch.setattr(hackernews, "_find_whoishiring_thread", lambda: "42123456")
    comments = [
        {
            "id": "999001",
            "type": "comment",
            "text": "<p>Acme | Remote | Staff Backend Engineer | Go</p>",
        },
        {"id": "999002", "type": "comment", "text": "short"},
    ]
    monkeypatch.setattr(hackernews, "_fetch_comments", lambda tid: comments if tid == "42123456" else [])

    listings = hackernews.scrape({"name": "HN Who's Hiring", "type": "hackernews"})

    assert len(listings) == 1  # short comment dropped
    assert listings[0]["url"] == "https://news.ycombinator.com/item?id=999001"
    assert listings[0]["title"] == "Staff Backend Engineer"
    assert listings[0]["location"] == "Remote"


def test_scrape_no_thread_prints_notice_and_returns_empty(monkeypatch, capsys):
    monkeypatch.setattr(hackernews, "_find_whoishiring_thread", lambda: None)
    monkeypatch.setattr(
        urllib.request, "urlopen", urlopen_returning(lambda url: json_body({"hits": []}))
    )

    assert hackernews.scrape({"name": "HN Who's Hiring"}) == []
    assert "Could not find Who's Hiring thread" in capsys.readouterr().out
