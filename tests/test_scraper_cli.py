"""Unit tests for top-level unified scraper CLI runner (scraper.py)."""

import sys
import subprocess


def test_scraper_help():
    res = subprocess.run(
        [sys.executable, "scraper.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    out = res.stdout
    assert "naukri" in out.lower() or "scraper" in out.lower()


def test_scraper_wellfound_help():
    res = subprocess.run(
        [sys.executable, "scraper.py", "wellfound", "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "wellfound" in res.stdout.lower()


def test_scraper_linkedin_help():
    res = subprocess.run(
        [sys.executable, "scraper.py", "linkedin", "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "linkedin" in res.stdout.lower()


def test_scraper_test_subcommand_sys_argv_preserved():
    """Verify that calling scraper.main with test subcommand does not mutate sys.argv."""
    from unittest.mock import patch
    import scraper

    original_argv = list(sys.argv)
    with patch("tests.test_inc42.main") as mock_inc42_main:
        scraper.main(["test", "inc42", "--company", "Zepto"])
        mock_inc42_main.assert_called_once()

    assert sys.argv == original_argv


def test_scraper_leads_help():
    res = subprocess.run(
        [sys.executable, "scraper.py", "leads", "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "lead" in res.stdout.lower()

