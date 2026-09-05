"""Feed vertical slices: one self-contained module per source type.

Each module owns its fetching, parsing, and registration (via @register from
jobtracker.registry). This __init__ auto-discovers every module in the
package, so adding a feed = dropping a new module here + one entry in
config/sources.yaml. Nothing else changes.
"""
import importlib
import pkgutil

for _mod in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_mod.name}")
