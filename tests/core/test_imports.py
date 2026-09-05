"""Import-lint: core is a shared kernel and never imports outward layers.

Spec ARCH-10: modules under core/ SHALL NOT import feeds, registry,
pipeline, or cli. Checked on the AST so it cannot rot silently.
"""
import ast
from pathlib import Path

import jobtracker.core

BANNED_PREFIXES = (
    "jobtracker.feeds",
    "jobtracker.registry",
    "jobtracker.pipeline",
    "jobtracker.cli",
    "feeds",
    "registry",
    "pipeline",
    "cli",
)

CORE_DIR = Path(jobtracker.core.__file__).resolve().parent


def _imports_of(tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.append(node.module)
    return found


def test_core_never_imports_outward_layers():
    violations = []
    for py in sorted(CORE_DIR.glob("*.py")):
        tree = ast.parse(py.read_text(), filename=str(py))
        for name in _imports_of(tree):
            if name.startswith(BANNED_PREFIXES):
                violations.append(f"{py.name}: {name}")
    assert violations == []
