"""Unit tests for naukri_scraper.config."""

from naukri_scraper.config import (
    NAUKRI_BASE_URL,
    NAUKRI_SITEMAP_INDEX_URL,
    JOB_FIELDS,
    COMPANY_FIELDS,
    DEFAULT_HEADERS,
)


def test_base_urls():
    assert "naukri.com" in NAUKRI_BASE_URL
    assert NAUKRI_SITEMAP_INDEX_URL.endswith(".xml")


def test_default_headers():
    assert "User-Agent" in DEFAULT_HEADERS
    assert "Mozilla" in DEFAULT_HEADERS["User-Agent"]


def test_job_fields_contains_required():
    required = [
        "title",
        "company",
        "company_website",
        "location",
        "url",
        "posted_date",
        "headquarters",
        "founders",
        "founding_year",
        "company_stage",
        "total_funding",
        "revenue",
    ]
    for field in required:
        assert field in JOB_FIELDS, f"Expected {field} in JOB_FIELDS"


def test_company_fields_contains_required():
    required = [
        "company_name",
        "company_website",
        "company_linkedin",
        "total_jobs_posted",
        "job_titles",
        "naukri_job_urls",
        "headquarters",
        "founders",
        "founding_year",
        "company_stage",
        "total_funding",
        "revenue",
    ]
    for field in required:
        assert field in COMPANY_FIELDS, f"Expected {field} in COMPANY_FIELDS"
