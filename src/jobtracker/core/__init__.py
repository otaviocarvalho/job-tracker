"""Shared kernel: cross-slice domain logic (scoring, dedup, digest, config).

Dependency rule (ARCH.md): nothing here may import jobtracker.feeds,
jobtracker.registry, jobtracker.pipeline, or jobtracker.cli.
"""
