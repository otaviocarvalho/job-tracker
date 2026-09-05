"""Feed registry: maps sources.yaml "type" to a scrape function.

The extension point of the tracker. Feeds register themselves with the
@register decorator when their module is imported (feeds/__init__.py
auto-discovers every module in the feeds package). This module never
imports the feeds package - registration only flows through the decorator,
which keeps registry <-> feeds free of circular imports.
"""
from typing import Callable

ScrapeFn = Callable[[dict], list[dict]]

_REGISTRY: dict[str, ScrapeFn] = {}


def register(feed_type: str):
    """Decorator storing a scrape function under a sources.yaml "type" key."""

    def deco(fn: ScrapeFn) -> ScrapeFn:
        _REGISTRY[feed_type] = fn
        return fn

    return deco


def get(feed_type: str) -> ScrapeFn | None:
    """Return the scrape function for a feed type, or None if unknown."""
    return _REGISTRY.get(feed_type)


def registered_types() -> list[str]:
    """Sorted feed types currently registered (for tests and debugging)."""
    return sorted(_REGISTRY)


def scrape_source(source: dict) -> list[dict]:
    """Dispatch one sources.yaml entry to its registered feed.

    Unknown types are reported the way the legacy dispatcher did (message on
    stdout, empty result) - never raised, so one bad config line cannot kill
    a digest run.
    """
    stype = source.get("type", "")
    fn = _REGISTRY.get(stype)
    if fn is None:
        print(f"  Unknown source type: {stype}")
        return []
    return fn(source)
