"""Unit tests for naukri_scraper.scraper (NaukriScraper class)."""

import gzip
from unittest.mock import patch
from naukri_scraper.scraper import NaukriScraper


def test_scraper_init():
    scraper = NaukriScraper(timeout=10, max_retries=2)
    assert scraper.timeout == 10
    assert scraper.max_retries == 2
    assert "User-Agent" in scraper.session.headers


def test_decompress_plain():
    scraper = NaukriScraper()
    plain_bytes = b"<xml>hello</xml>"
    result = scraper._decompress_if_needed(plain_bytes, "http://example.com/sitemap.xml")
    assert result == "<xml>hello</xml>"


def test_decompress_gzip():
    scraper = NaukriScraper()
    content = "<xml>zipped content</xml>"
    gz_bytes = gzip.compress(content.encode("utf-8"))
    result = scraper._decompress_if_needed(gz_bytes, "http://example.com/sitemap.xml.gz")
    assert result == content


def test_get_target_sitemaps_city():
    scraper = NaukriScraper()
    with patch.object(scraper, "_fetch", return_value=None):
        sitemaps = scraper.get_target_sitemaps(location_filter="Bangalore")
        assert any("jobDescPagesBangalore.xml" in s for s in sitemaps)


def test_stream_job_urls():
    scraper = NaukriScraper()
    mock_xml = b"""
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://www.naukri.com/job-listings-python-dev-123</loc></url>
        <url><loc>https://www.naukri.com/job-listings-react-dev-456</loc></url>
        <url><loc>https://www.naukri.com/other-page</loc></url>
    </urlset>
    """
    with patch.object(scraper, "_fetch", return_value=mock_xml):
        urls = list(scraper.stream_job_urls("http://example.com/sitemap.xml"))
        assert len(urls) == 2
        assert "job-listings-python-dev-123" in urls[0]
        assert "job-listings-react-dev-456" in urls[1]
