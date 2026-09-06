"""Unit tests for naukri_scraper.parser."""

import datetime
from naukri_scraper.parser import parse_job_url, matches_filters


def test_parse_job_url_valid():
    url = "https://www.naukri.com/job-listings-python-backend-developer-acme-technologies-bengaluru-3-to-6-years-250826021510"
    job = parse_job_url(url)
    assert job is not None
    assert job["job_id"] == "250826021510"
    assert "Python" in job["title"]
    assert "Bengaluru" in job["location"]
    assert job["min_experience"] == 3
    assert job["max_experience"] == 6
    assert job["experience_text"] == "3-6 yrs"
    assert job["posted_date"] == "2026-08-25"
    assert job["source"] == "naukri"


def test_parse_job_url_invalid():
    assert parse_job_url("") is None
    assert parse_job_url("https://www.google.com") is None
    assert parse_job_url("https://www.naukri.com/browse-jobs") is None


def test_matches_filters_keywords():
    job = {
        "title": "Senior Python Engineer",
        "company": "Tech Corp",
        "location": "Bengaluru",
        "min_experience": 2,
        "max_experience": 5,
        "_posted_date_obj": datetime.date(2026, 8, 25),
        "url": "https://naukri.com/job-123",
    }
    assert matches_filters(job, keywords=["python"])
    assert matches_filters(job, keywords=["PYTHON"])
    assert not matches_filters(job, keywords=["java", "golang"])


def test_matches_filters_location():
    job = {
        "title": "Frontend Lead",
        "company": "Corp",
        "location": "Mumbai, Pune",
        "min_experience": 4,
        "max_experience": 8,
        "_posted_date_obj": datetime.date(2026, 8, 25),
        "url": "https://naukri.com/job-456",
    }
    assert matches_filters(job, location_filter="Mumbai")
    assert matches_filters(job, location_filter="pune")
    assert not matches_filters(job, location_filter="Hyderabad")


def test_matches_filters_experience():
    job = {
        "title": "Data Analyst",
        "company": "Data Inc",
        "location": "Delhi",
        "min_experience": 2,
        "max_experience": 5,
        "_posted_date_obj": datetime.date(2026, 8, 25),
        "url": "https://naukri.com/job-789",
    }
    assert matches_filters(job, experience_filter=3)
    assert matches_filters(job, experience_filter=2)
    assert matches_filters(job, experience_filter=5)
    assert not matches_filters(job, experience_filter=1)
    assert not matches_filters(job, experience_filter=6)


def test_matches_filters_date():
    job_recent = {
        "title": "Engineer",
        "company": "A",
        "location": "Remote",
        "min_experience": 0,
        "max_experience": 10,
        "_posted_date_obj": datetime.date(2026, 8, 25),
        "url": "https://naukri.com/job-1",
    }
    assert matches_filters(job_recent, since_date=datetime.date(2026, 8, 20))
    assert matches_filters(job_recent, since_date=datetime.date(2026, 8, 25))
    assert not matches_filters(job_recent, since_date=datetime.date(2026, 8, 26))
