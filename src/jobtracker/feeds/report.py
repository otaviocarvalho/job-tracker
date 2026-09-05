"""Report-type feed slice: sources that need manual review (no scraping).

Ramp Vendor Reports, Harmonic Hot 25, Founders You Should Know. These are
listed in sources.yaml for reference; the slice surfaces the manual-review
notice in the run output and contributes zero listings.
"""
from jobtracker.registry import register


@register("report")
def scrape(source: dict) -> list[dict]:
    """Report-type sources need manual review: print the notice, return none."""
    name = source.get("name", "")
    url = source.get("url", "")
    print(f"  [report:{name}] Report-type sources need manual review: {url}")
    return []
