"""Substack slice tests: RSS extraction, publication/url variants, error convention."""
import urllib.error
import urllib.request

from conftest import urlopen_raising, urlopen_returning
from jobtracker.feeds import substack

RSS = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<rss version="2.0"><channel><title>NP</title>'
    b"<item><title>Post One</title><link>https://nextplay.example/p/1</link>"
    b"<description>&lt;p&gt;Jobs at Acme&lt;/p&gt;</description></item>"
    b"<item><title>Post Two</title><link>https://nextplay.example/p/2</link>"
    b"<description>plain text</description></item>"
    b"<item><link>https://nextplay.example/p/3</link>"
    b"<description>no title, skipped</description></item>"
    b"</channel></rss>"
)

SOURCE = {
    "name": "Next Play Newsletter",
    "type": "substack",
    "url": "https://nextplay.substack.com",
    "config": {"publication": "nextplay"},
}


def test_scrape_publication_variant_fetches_substack_feed(monkeypatch):
    seen = []
    monkeypatch.setattr(urllib.request, "urlopen", urlopen_returning(lambda url: seen.append(url) or RSS))

    listings = substack.scrape(SOURCE)

    assert seen == ["https://nextplay.substack.com/feed"]
    assert len(listings) == 2  # titleless item skipped
    assert listings[0]["title"] == "[Newsletter] Post One"
    assert listings[0]["description"] == "Jobs at Acme"  # description tags stripped
    assert listings[0]["url"] == "https://nextplay.example/p/1"
    assert listings[0]["source"] == "Next Play Newsletter"
    assert listings[0]["company"] == "Next Play Newsletter"


def test_scrape_url_variant_appends_feed_path(monkeypatch):
    seen = []
    monkeypatch.setattr(urllib.request, "urlopen", urlopen_returning(lambda url: seen.append(url) or RSS))

    substack.scrape({"name": "Custom", "type": "substack", "url": "https://letters.example/"})

    assert seen == ["https://letters.example/feed"]


def test_scrape_requires_publication_or_url(capsys):
    assert substack.scrape({"name": "Broken", "type": "substack"}) == []
    assert "No publication or URL provided for Broken" in capsys.readouterr().out


def test_scrape_error_returns_empty_and_prints(monkeypatch, capsys):
    monkeypatch.setattr(
        urllib.request, "urlopen", urlopen_raising(urllib.error.URLError("timeout"))
    )
    assert substack.scrape(SOURCE) == []
    assert "[substack:nextplay] Error:" in capsys.readouterr().out
