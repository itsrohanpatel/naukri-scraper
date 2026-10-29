"""Unit tests for naukri_scraper.cli and wellfound_cli argument parsers."""

from naukri_scraper.cli import parse_args as parse_naukri_args
from naukri_scraper.wellfound_cli import parse_args as parse_wf_args


def test_naukri_cli_defaults():
    args = parse_naukri_args([])
    assert args.keywords == ["python"]
    assert args.output == "naukri_companies.csv"
    assert not args.inc42_only
    assert not args.verbose


def test_naukri_cli_custom():
    args = parse_naukri_args([
        "--url", "https://naukri.com/jobs",
        "--pages", "3",
        "--inc42-only",
        "--output", "custom.csv",
    ])
    assert args.url == "https://naukri.com/jobs"
    assert args.pages == 3
    assert args.inc42_only
    assert args.output == "custom.csv"


def test_wellfound_cli_args():
    args = parse_wf_args([
        "--url", "https://wellfound.com/jobs",
        "--days", "7",
        "--workers", "4",
        "--output", "wf.csv",
    ])
    assert args.url == "https://wellfound.com/jobs"
    assert args.days == 7
    assert args.workers == 4
    assert args.output == "wf.csv"


def test_naukri_cli_leads_args():
    args = parse_naukri_args(["--leads", "--leads-output", "data/custom_leads.csv"])
    assert args.leads is True
    assert args.leads_output == "data/custom_leads.csv"
