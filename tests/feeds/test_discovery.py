"""Auto-discovery tests (ARCH-04, ARCH-05): package scan, zero-touch registration."""
import importlib
from pathlib import Path

import jobtracker.feeds as feeds
import jobtracker.registry as registry

EXPECTED_TYPES = ["greenhouse", "hackernews", "infranyc", "report", "speedrun", "substack", "ycombinator"]


def test_all_builtin_feed_types_registered():
    assert registry.registered_types() == EXPECTED_TYPES


def test_zero_touch_registration_of_new_module():
    # spec ARCH-05: dropping a new module into feeds/ registers it with NO
    # edits to any other module (no import list, no dispatcher change)
    probe = Path(feeds.__file__).parent / "zz_discovery_probe.py"
    probe.write_text(
        "from jobtracker.registry import register\n"
        "\n"
        "@register('zzprobe')\n"
        "def scrape(source):\n"
        "    return [{'title': 'probe'}]\n"
    )
    try:
        importlib.reload(feeds)
        assert "zzprobe" in registry.registered_types()
        assert registry.get("zzprobe")({"name": "x"}) == [{"title": "probe"}]
    finally:
        probe.unlink(missing_ok=True)
        registry._REGISTRY.pop("zzprobe", None)
        importlib.reload(feeds)


def test_discovery_is_idempotent_on_reload():
    importlib.reload(feeds)
    assert registry.registered_types() == EXPECTED_TYPES
