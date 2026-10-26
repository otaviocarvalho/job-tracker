"""Config loader tests (ARCH-12: single shared loader, repo-root resolution)."""
from jobtracker.core import config


def test_repo_root_resolves_to_repo_layout():
    root = config.repo_root()
    assert (root / "config" / "sources.yaml").is_file()
    assert (root / "config" / "criteria.yaml").is_file()
    assert (root / "main.py").is_file()


def test_load_sources_returns_all_registered_sources():
    sources = config.load_sources()
    assert len(sources) == 34  # 22 scraped feed entries + 12 manual/report sources
    assert sources[0]["name"] == "a16z Portfolio"
    names = [s["name"] for s in sources]
    assert "HN Who's Hiring" in names
    assert "infra.nyc" in names
    assert "xAI" in names  # AD-0007: London/EMEA/remote watchlist entry


def test_load_sources_entries_carry_type_and_url():
    sources = config.load_sources()
    entry = next(s for s in sources if s["type"] == "greenhouse")
    assert entry["config"]["board"] == "a16z"
    assert entry["url"].startswith("https://")


def test_xai_source_carries_location_include_filter():
    entry = next(s for s in config.load_sources() if s["name"] == "xAI")
    assert entry["config"]["board"] == "xai"
    assert entry["config"]["trending"] is True
    patterns = [p.lower() for p in entry["config"]["location_include"]]
    assert "london" in patterns and "emea" in patterns
    assert "remote international" in patterns
    assert "remote us" not in patterns  # US-only remote stays out


def test_load_criteria_values_used_by_scoring():
    c = config.load_criteria()
    assert c["strong_match_threshold"] == 70
    assert c["worth_a_look_threshold"] == 45
    assert c["positive_title_keywords"]["staff"] == 20
    assert "frontend" in c["reject_title_keywords"]
    assert c["digest_max_per_company"] == 3
    assert "solutions engineer" in c["reject_title_keywords"]
    assert "india" in c["reject_location_keywords"]


def test_load_groups_shipped_yaml():
    """GRP-08: three production groups ship in order with their gates."""
    groups = config.load_groups()
    assert [g["name"] for g in groups] == ["global", "emea", "spain-bcn"]
    assert [g["label"] for g in groups] == [
        "Global",
        "EMEA",
        "Spain Remote + Barcelona",
    ]
    assert groups[0]["require_location_keywords"] == []
    assert groups[0]["trending_manual"] is True
    emea = groups[1]["require_location_keywords"]
    assert "emea" in emea and "europe" in emea and "barcelona" in emea
    assert "uk" in emea and "united kingdom" in emea
    spain = groups[2]["require_location_keywords"]
    assert "spain" in spain and "barcelona" in spain and "españa" in spain
    assert all(g["sources"] is None for g in groups)


def test_load_groups_missing_file_fallback(tmp_path, monkeypatch):
    """GRP-01: no groups.yaml -> single global group."""
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    assert config.load_groups() == [{"name": "global", "label": "Global"}]


def test_load_groups_normalization(tmp_path, monkeypatch):
    """GRP-01: lowering, label default, sources subset, trending flag."""
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    (tmp_path / "groups.yaml").write_text(
        "groups:\n"
        "  - name: eu-only\n"
        "    require_location_keywords: [Europe, EMEA]\n"
        "    sources: [HN Who's Hiring, YC Companies]\n"
        "  - name: tagged\n"
        "    label: Tagged\n"
        "    trending_manual: true\n"
    )
    groups = config.load_groups()
    assert groups[0]["label"] == "eu-only"  # label defaults to name
    assert groups[0]["require_location_keywords"] == ["europe", "emea"]
    assert groups[0]["sources"] == ["HN Who's Hiring", "YC Companies"]
    assert groups[0]["trending_manual"] is False
    assert groups[1]["label"] == "Tagged"
    assert groups[1]["sources"] is None
    assert groups[1]["trending_manual"] is True


def test_load_groups_empty_yaml_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    (tmp_path / "groups.yaml").write_text("groups: []\n")
    assert config.load_groups() == [{"name": "global", "label": "Global"}]
