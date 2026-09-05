"""Registry tests (ARCH-06, ARCH-07): registration, dispatch contract, unknown type.

Each test swaps _REGISTRY via monkeypatch so global state never leaks
between test files (feeds discovery tests rely on the populated registry).
"""
import ast
from pathlib import Path

import jobtracker.registry as registry


def test_register_decorator_stores_function(monkeypatch):
    registry._REGISTRY = {}

    @registry.register("faketest")
    def scrape(source):
        return []

    assert registry.get("faketest") is scrape


def test_registered_types_is_sorted_view(monkeypatch):
    registry._REGISTRY = {}
    registry.register("b")((lambda s: []))
    registry.register("a")((lambda s: []))
    assert registry.registered_types() == ["a", "b"]


def test_get_unknown_type_returns_none():
    assert registry.get("no-such-type-xyz") is None


def test_scrape_source_passes_full_source_entry_to_feed(monkeypatch, capsys):
    registry._REGISTRY = {}
    received = {}

    @registry.register("fullentry")
    def scrape(source):
        received.update(source)
        return [{"title": "x"}]

    source = {
        "name": "Full Entry",
        "type": "fullentry",
        "url": "https://example.com",
        "config": {"board": "acme"},
    }
    result = registry.scrape_source(source)

    assert result == [{"title": "x"}]
    # the feed receives the whole YAML entry, not a projection of it
    assert received == source


def test_scrape_source_unknown_type_prints_and_returns_empty(capsys):
    assert registry.scrape_source({"name": "Ghost", "type": "ghost", "url": ""}) == []
    assert capsys.readouterr().out == "  Unknown source type: ghost\n"


def test_scrape_source_missing_type_key_prints_empty_type(capsys):
    assert registry.scrape_source({"name": "Broken"}) == []
    assert capsys.readouterr().out == "  Unknown source type: \n"


def test_registry_module_never_imports_feeds():
    # design rule: no registry -> feeds import (avoids the circular import)
    src = Path(registry.__file__).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(not alias.name.startswith("jobtracker.feeds") for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("jobtracker.feeds")
