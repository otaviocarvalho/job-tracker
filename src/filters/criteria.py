"""Load criteria from YAML config."""
import yaml
from pathlib import Path

CRITERIA_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "criteria.yaml"


def load() -> dict:
    with open(CRITERIA_PATH) as f:
        return yaml.safe_load(f)
