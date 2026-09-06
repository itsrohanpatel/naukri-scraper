"""Unit tests for naukri_scraper.wellfound_scraper."""

from naukri_scraper.wellfound_scraper import (
    parse_posted_age_days,
    clean_company_name_for_search,
    filter_and_aggregate_companies,
)


def test_parse_posted_age_days():
    assert parse_posted_age_days("Just now") == 0.0
    assert parse_posted_age_days("today") == 0.0
    assert parse_posted_age_days("yesterday") == 1.0
    assert parse_posted_age_days("12 hours ago") == 0.5
    assert parse_posted_age_days("2 days ago") == 2.0
    assert parse_posted_age_days("3 weeks ago") == 21.0
    assert parse_posted_age_days("1 month ago") == 30.0
    assert parse_posted_age_days("") == 999.0
    assert parse_posted_age_days("unknown date") == 999.0


def test_clean_company_name_for_search():
    assert clean_company_name_for_search("Acme Technologies Pvt Ltd") == "Acme"
    assert clean_company_name_for_search("Stripe (Fintech)") == "Stripe"
    assert clean_company_name_for_search("Razorpay Software Private Limited") == "Razorpay"


def test_filter_and_aggregate_companies():
    mock_raw_jobs = [
        {
            "company_name": "Startup Alpha",
            "company_slug": "/company/startup-alpha",
            "job_title": "Full Stack Engineer",
            "job_url": "https://wellfound.com/jobs/111",
            "posted_date_raw": "2 days ago",
            "posted_age_days": 2.0,
            "location": "Bengaluru",
            "salary": "$80k - $100k",
            "equity": "0.1% - 0.5%",
            "stage": "Seed",
            "employee_count": "11-50 Employees",
        },
        {
            "company_name": "Startup Alpha",
            "company_slug": "/company/startup-alpha",
            "job_title": "Backend Engineer",
            "job_url": "https://wellfound.com/jobs/112",
            "posted_date_raw": "1 day ago",
            "posted_age_days": 1.0,
            "location": "Remote",
            "salary": "$90k - $110k",
            "equity": "0.1%",
            "stage": "Seed",
            "employee_count": "11-50 Employees",
        },
        {
            "company_name": "Old Corp",
            "company_slug": "/company/old-corp",
            "job_title": "Legacy Architect",
            "job_url": "https://wellfound.com/jobs/222",
            "posted_date_raw": "20 days ago",
            "posted_age_days": 20.0,
            "location": "Mumbai",
            "salary": "",
            "equity": "",
            "stage": "Series C",
            "employee_count": "500+ Employees",
        },
    ]

    # Filter with max_days=7
    filtered = filter_and_aggregate_companies(mock_raw_jobs, max_days=7.0)
    assert len(filtered) == 1
    alpha = filtered[0]
    assert alpha["company_name"] == "Startup Alpha"
    assert alpha["total_jobs_posted"] == 2
    assert len(alpha["job_titles"]) == 2
    assert "Full Stack Engineer" in alpha["job_titles"]
    assert "Backend Engineer" in alpha["job_titles"]
    assert "Bengaluru" in alpha["locations"]
    assert "Remote" in alpha["locations"]

    # Filter with location="Mumbai"
    mumbai_filtered = filter_and_aggregate_companies(mock_raw_jobs, location_filter="Mumbai")
    assert len(mumbai_filtered) == 1
    assert mumbai_filtered[0]["company_name"] == "Old Corp"
