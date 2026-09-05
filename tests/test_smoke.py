"""Smoke tests: package imports and runtime dependencies are present."""


def test_package_imports():
    import jobtracker

    assert jobtracker.__version__ == "0.2.0"


def test_runtime_dependency_pyyaml_present():
    import yaml

    assert yaml.__version__.startswith("6.")
