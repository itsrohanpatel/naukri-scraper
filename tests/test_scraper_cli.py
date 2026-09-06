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

