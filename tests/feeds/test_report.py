"""Report slice tests: manual-review notice with zero listings (legacy else-branch output)."""
from jobtracker.feeds import report


def test_report_prints_manual_review_notice_and_returns_empty(capsys):
    out = report.scrape(
        {"name": "Ramp Vendor Reports", "type": "report", "url": "https://ramp.com/data"}
    )

    assert out == []
    assert capsys.readouterr().out == (
        "  [report:Ramp Vendor Reports] Report-type sources need manual review: https://ramp.com/data\n"
    )
