"""Config loader tests (ARCH-12: single shared loader, repo-root resolution)."""
from jobtracker.core import config


def test_repo_root_resolves_to_repo_layout():
    root = config.repo_root()
    assert (root / "config" / "sources.yaml").is_file()
    assert (root / "config" / "criteria.yaml").is_file()
    assert (root / "main.py").is_file()


def test_load_sources_returns_all_registered_sources():
    sources = config.load_sources()
    assert len(sources) == 11  # 8 scraped feeds + 3 manual report sources
    assert sources[0]["name"] == "a16z Portfolio"
    names = [s["name"] for s in sources]
    assert "HN Who's Hiring" in names
    assert "infra.nyc" in names


def test_load_sources_entries_carry_type_and_url():
    sources = config.load_sources()
    entry = next(s for s in sources if s["type"] == "greenhouse")
    assert entry["config"]["board"] == "a16z"
    assert entry["url"].startswith("https://")


def test_load_criteria_values_used_by_scoring():
    c = config.load_criteria()
    assert c["strong_match_threshold"] == 70
    assert c["worth_a_look_threshold"] == 45
    assert c["positive_title_keywords"]["staff"] == 20
    assert "frontend" in c["reject_title_keywords"]
