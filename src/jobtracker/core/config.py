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


def _default_group() -> list[dict]:
    return [{"name": "global", "label": "Global"}]


def load_groups() -> list[dict]:
    """Load search groups from config/groups.yaml (AD-0008).

    Each entry normalizes to {name, label, require_location_keywords (lowered
    list), sources (subset list or None for all), trending_manual (bool)}.
    Missing or empty file falls back to a single global group so the loader
    never returns nothing.
    """
    path = CONFIG_DIR / "groups.yaml"
    if not path.exists():
        return _default_group()
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    groups = []
    for i, entry in enumerate(raw.get("groups") or []):
        name = str(entry.get("name") or f"group-{i + 1}")
        groups.append(
            {
                "name": name,
                "label": str(entry.get("label") or name),
                "require_location_keywords": [
                    str(k).lower()
                    for k in (entry.get("require_location_keywords") or [])
                ],
                "sources": [str(s) for s in (entry.get("sources") or [])] or None,
                "trending_manual": bool(entry.get("trending_manual", False)),
            }
        )
    return groups or _default_group()
