"""Job Tracker - vertical feed slices over a shared scoring/dedup core.

Layout (see ARCH.md):
    jobtracker.core       scoring, dedup store, digest, config loaders
    jobtracker.registry   feed registry: sources.yaml "type" -> scrape function
    jobtracker.feeds      one self-contained vertical slice per feed type
    jobtracker.pipeline   orchestration: scrape -> score -> dedup -> digest
    jobtracker.cli        argparse entrypoint used by main.py
"""

__version__ = "0.2.0"
