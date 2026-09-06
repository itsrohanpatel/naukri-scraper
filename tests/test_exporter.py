"""Unit tests for naukri_scraper.exporter."""

import csv
import json
from pathlib import Path
from naukri_scraper.exporter import (
    aggregate_companies,
    save_to_csv,
    save_to_json,
)


def test_aggregate_companies():
    mock_jobs = [
        {
            "title": "Backend Python Dev",
            "company": "Acme Corp",
            "company_website": "https://acme.com",
            "company_linkedin": "https://linkedin.com/company/acme",
            "location": "Bengaluru",
            "experience_text": "3-5 yrs",
            "salary": "15-20 Lacs",
            "skills": "Python, Django",
            "posted_date": "2026-08-20",
            "url": "https://naukri.com/job-1",
            "headquarters": "Bengaluru, India",
            "founders": "John Doe, Jane Smith",
            "founding_year": "2019",
            "company_stage": "Series B",
            "total_funding": "$30M",
            "revenue": "$10M",
        },
        {
            "title": "Senior Frontend Dev",
            "company": "Acme Corp",
            "company_website": "",
            "location": "Pune",
            "experience_text": "5-8 yrs",
            "salary": "Not disclosed",
            "skills": "React, TypeScript",
            "posted_date": "2026-08-25",
            "url": "https://naukri.com/job-2",
        },
        {
            "title": "DevOps Engineer",
            "company": "Beta LLC",
            "company_website": "https://beta.io",
            "location": "Mumbai",
            "experience_text": "2-4 yrs",
            "salary": "Not disclosed",
            "skills": "AWS, Docker",
            "posted_date": "2026-08-22",
            "url": "https://naukri.com/job-3",
        },
    ]

    aggregated = aggregate_companies(mock_jobs)
    assert len(aggregated) == 2

    # Acme Corp posted 2 jobs, should be first
    acme = aggregated[0]
    assert acme["company_name"] == "Acme Corp"
    assert acme["total_jobs_posted"] == 2
    assert acme["company_website"] == "https://acme.com"
    assert acme["company_linkedin"] == "https://linkedin.com/company/acme"
    assert "Backend Python Dev" in acme["job_titles"]
    assert "Senior Frontend Dev" in acme["job_titles"]
    assert "Bengaluru" in acme["locations"]
    assert "Pune" in acme["locations"]
    assert acme["latest_posted_date"] == "2026-08-25"
    assert acme["headquarters"] == "Bengaluru, India"
    assert acme["founders"] == "John Doe, Jane Smith"
    assert acme["company_stage"] == "Series B"


def test_save_to_csv_and_json(tmp_path: Path):
    mock_jobs = [
        {
            "title": "Software Engineer",
            "company": "Test Co",
            "company_website": "https://test.co",
            "location": "Remote",
            "experience_text": "1-3 yrs",
            "salary": "10-12 Lacs",
            "url": "https://naukri.com/job-100",
            "posted_date": "2026-08-01",
            "source": "naukri",
        }
    ]

    csv_file = tmp_path / "test_jobs.csv"
    saved_csv = save_to_csv(mock_jobs, str(csv_file))
    assert saved_csv.exists()

    with open(saved_csv, mode="r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 1
        assert reader[0]["company"] == "Test Co"

    json_file = tmp_path / "test_jobs.json"
    saved_json = save_to_json(mock_jobs, str(json_file))
    assert saved_json.exists()

    with open(saved_json, mode="r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["company"] == "Test Co"
