"""Repo layout resolution and YAML config loaders (single source of truth)."""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"


def repo_root() -> Path:
    """Absolute path of the repository root (parent of src/)."""
    return REPO_ROOT


def load_sources() -> list[dict]:
    """Load the feed registry from config/sources.yaml."""
    with open(CONFIG_DIR / "sources.yaml") as f:
        return yaml.safe_load(f).get("sources", [])


def load_criteria() -> dict:
    """Load profile scoring criteria from config/criteria.yaml."""
    with open(CONFIG_DIR / "criteria.yaml") as f:
        return yaml.safe_load(f)
