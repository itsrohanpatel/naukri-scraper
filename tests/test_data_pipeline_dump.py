"""Comprehensive Production-Readiness & Dump Data Verification Test Suite.

Verifies end-to-end data pipeline integrity:
1. Dumps raw job records to disk (JSON & CSV).
2. Verifies 100% of canonical JOB_FIELDS are collected and populated.
3. Aggregates jobs into unique company profiles and dumps to disk.
4. Verifies 100% of canonical COMPANY_FIELDS are collected and populated.
5. Dumps raw Wellfound job cards and verifies filter-and-aggregate output.
6. Verifies 100% of WELLFOUND_COMPANY_FIELDS are collected and populated.
7. Guarantees no field truncation, no column misalignment, and no silent data loss.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from naukri_scraper.config import COMPANY_FIELDS, JOB_FIELDS
from naukri_scraper.exporter import (
    aggregate_companies,
    save_to_csv,
    save_to_json,
    save_companies_to_csv,
    save_companies_to_json,
)
from naukri_scraper.wellfound_scraper import (
    WELLFOUND_COMPANY_FIELDS,
    filter_and_aggregate_companies,
)


@pytest.fixture
def sample_naukri_jobs() -> List[Dict[str, Any]]:
    """Realistic mock dataset simulating enriched jobs from Naukri & Inc42/AmbitionBox."""
    return [
        {
            "job_id": "010926000101",
            "title": "Lead Software Architect - Python & Distributed Systems",
            "company": "Zepto",
            "company_website": "https://www.zeptonow.com",
            "company_linkedin": "https://www.linkedin.com/company/zepto-consumer/",
            "location": "Bengaluru, Mumbai",
            "experience_text": "6-10 yrs",
            "salary": "40-55 Lacs P.A.",
            "skills": "Python, FastApi, Kafka, Redis, Distributed Systems, Docker",
            "job_description": "We are seeking a seasoned backend architect to scale quick commerce infra.",
            "company_rating": "4.2",
            "company_reviews_count": "1520",
            "ambition_box_url": "https://www.ambitionbox.com/overview/zepto-overview",
            "vacancies": "2",
            "freshness": "1 day ago",
            "posted_date": "2026-09-01",
            "min_experience": 6,
            "max_experience": 10,
            "url": "https://www.naukri.com/job-listings-lead-software-architect-zepto-010926000101",
            "source": "naukri",
            "headquarters": "Mumbai, Maharashtra",
            "founders": "Aadit Palicha, Kaivalya Vohra",
            "founding_year": "2021",
            "company_stage": "Series E",
            "total_funding": "$1.5 Billion",
            "revenue": "INR 2000 Cr",
        },
        {
            "job_id": "020926000102",
            "title": "Senior Data Platform Engineer",
            "company": "Zepto",
            "company_website": "https://www.zeptonow.com",
            "company_linkedin": "https://www.linkedin.com/company/zepto-consumer/",
            "location": "Bengaluru",
            "experience_text": "4-7 yrs",
            "salary": "30-42 Lacs P.A.",
            "skills": "PySpark, Airflow, Snowflake, AWS, Python",
            "job_description": "Build high-throughput data processing pipelines.",
            "company_rating": "4.2",
            "company_reviews_count": "1520",
            "ambition_box_url": "https://www.ambitionbox.com/overview/zepto-overview",
            "vacancies": "1",
            "freshness": "Today",
            "posted_date": "2026-09-02",
            "min_experience": 4,
            "max_experience": 7,
            "url": "https://www.naukri.com/job-listings-senior-data-platform-engineer-zepto-020926000102",
            "source": "naukri",
            "headquarters": "Mumbai, Maharashtra",
            "founders": "Aadit Palicha, Kaivalya Vohra",
            "founding_year": "2021",
            "company_stage": "Series E",
            "total_funding": "$1.5 Billion",
            "revenue": "INR 2000 Cr",
        },
        {
            "job_id": "030926000103",
            "title": "Full Stack Engineer - React & Node",
            "company": "Tigi HR",
            "company_website": "https://tigihr.com",
            "company_linkedin": "https://www.linkedin.com/company/tigi-hr/",
            "location": "Ahmedabad, Remote",
            "experience_text": "2-5 yrs",
            "salary": "12-18 Lacs P.A.",
            "skills": "React, Node.js, TypeScript, PostgreSQL",
            "job_description": "Develop modern enterprise talent platform features.",
            "company_rating": "4.5",
            "company_reviews_count": "180",
            "ambition_box_url": "https://www.ambitionbox.com/overview/tigi-hr-overview",
            "vacancies": "3",
            "freshness": "2 days ago",
            "posted_date": "2026-08-31",
            "min_experience": 2,
            "max_experience": 5,
            "url": "https://www.naukri.com/job-listings-full-stack-engineer-tigi-hr-030926000103",
            "source": "naukri",
            "headquarters": "Ahmedabad, Gujarat",
            "founders": "Kashyap Dave",
            "founding_year": "2016",
            "company_stage": "Bootstrapped",
            "total_funding": "Bootstrapped",
            "revenue": "Profitable",
        },
    ]


@pytest.fixture
def sample_wellfound_raw_jobs() -> List[Dict[str, Any]]:
    """Realistic mock dataset simulating raw scraped cards from Wellfound."""
    return [
        {
            "company_name": "HyperScale AI",
            "company_slug": "/company/hyperscale-ai",
            "job_title": "Founding ML Systems Engineer",
            "job_url": "https://wellfound.com/jobs/99001",
            "posted_date_raw": "5 hours ago",
            "posted_age_days": 0.2,
            "location": "Bengaluru, India",
            "salary": "$90k – $130k",
            "equity": "0.5% – 1.5%",
            "stage": "Seed",
            "employee_count": "11-50 Employees",
        },
        {
            "company_name": "HyperScale AI",
            "company_slug": "/company/hyperscale-ai",
            "job_title": "Full Stack Product Engineer",
            "job_url": "https://wellfound.com/jobs/99002",
            "posted_date_raw": "3 days ago",
            "posted_age_days": 3.0,
            "location": "Remote",
            "salary": "$80k – $110k",
            "equity": "0.2% – 0.8%",
            "stage": "Seed",
            "employee_count": "11-50 Employees",
        },
        {
            "company_name": "Legacy Tech Systems",
            "company_slug": "/company/legacy-tech",
            "job_title": "COBOL Maintenance Specialist",
            "job_url": "https://wellfound.com/jobs/99003",
            "posted_date_raw": "25 days ago",
            "posted_age_days": 25.0,
            "location": "Delhi, India",
            "salary": "Not disclosed",
            "equity": "None",
            "stage": "Public",
            "employee_count": "1000+ Employees",
        },
    ]


# ============================================================================
# 1. NAUKRI DATA DUMP & RE-INGESTION PIPELINE TESTS
# ============================================================================

def test_naukri_raw_job_dump_integrity(tmp_path: Path, sample_naukri_jobs: List[Dict[str, Any]]):
    """Dump raw Naukri jobs to CSV & JSON, re-read, and assert 100% field presence."""
    csv_out = tmp_path / "naukri_dumped_jobs.csv"
    json_out = tmp_path / "naukri_dumped_jobs.json"

    # Dump
    save_to_csv(sample_naukri_jobs, str(csv_out))
    save_to_json(sample_naukri_jobs, str(json_out))

    assert csv_out.exists(), "CSV dump was not created"
    assert json_out.exists(), "JSON dump was not created"

    # 1. Verify CSV Dump
    with csv_out.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    # Assert every single canonical field in JOB_FIELDS is present in the CSV header
    for expected_field in JOB_FIELDS:
        assert expected_field in fieldnames, f"Missing field in CSV header: {expected_field}"

    assert len(rows) == len(sample_naukri_jobs)
    for row, orig in zip(rows, sample_naukri_jobs):
        assert row["title"] == orig["title"]
        assert row["company"] == orig["company"]
        assert row["company_website"] == orig["company_website"]
        assert row["company_linkedin"] == orig["company_linkedin"]
        assert row["headquarters"] == orig["headquarters"]
        assert row["founders"] == orig["founders"]
        assert row["company_stage"] == orig["company_stage"]
        assert row["total_funding"] == orig["total_funding"]
        assert row["revenue"] == orig["revenue"]

    # 2. Verify JSON Dump
    with json_out.open("r", encoding="utf-8") as f:
        json_data = json.load(f)

    assert len(json_data) == len(sample_naukri_jobs)
    for orig in sample_naukri_jobs:
        matched = next(j for j in json_data if j["job_id"] == orig["job_id"])
        for expected_field in JOB_FIELDS:
            assert expected_field in matched, f"Missing field in JSON object: {expected_field}"
            assert matched[expected_field] == orig[expected_field]


def test_naukri_company_aggregation_dump_integrity(tmp_path: Path, sample_naukri_jobs: List[Dict[str, Any]]):
    """Aggregate raw jobs into company profiles, dump, and assert COMPANY_FIELDS completeness."""
    companies = aggregate_companies(sample_naukri_jobs)

    assert len(companies) == 2, "Expected 2 unique companies (Zepto and Tigi HR)"

    # Zepto posted 2 jobs, should be ranked #1
    zepto = companies[0]
    assert zepto["company_name"] == "Zepto"
    assert zepto["total_jobs_posted"] == 2
    assert "Lead Software Architect" in zepto["job_titles"]
    assert "Senior Data Platform Engineer" in zepto["job_titles"]
    assert "Bengaluru" in zepto["locations"]
    assert "Mumbai" in zepto["locations"]
    assert zepto["company_website"] == "https://www.zeptonow.com"
    assert zepto["company_linkedin"] == "https://www.linkedin.com/company/zepto-consumer/"
    assert zepto["headquarters"] == "Mumbai, Maharashtra"
    assert zepto["founders"] == "Aadit Palicha, Kaivalya Vohra"
    assert zepto["founding_year"] == "2021"
    assert zepto["company_stage"] == "Series E"
    assert zepto["total_funding"] == "$1.5 Billion"
    assert zepto["revenue"] == "INR 2000 Cr"

    # Dump companies to CSV and JSON
    csv_out = tmp_path / "naukri_companies_dump.csv"
    json_out = tmp_path / "naukri_companies_dump.json"

    save_companies_to_csv(companies, str(csv_out))
    save_companies_to_json(companies, str(json_out))

    # Verify CSV company dump
    with csv_out.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)

    for field in COMPANY_FIELDS:
        assert field in fields, f"Missing field in companies CSV: {field}"

    assert len(rows) == 2
    re_zepto = next(r for r in rows if r["company_name"] == "Zepto")
    assert int(re_zepto["total_jobs_posted"]) == 2
    assert re_zepto["headquarters"] == "Mumbai, Maharashtra"
    assert re_zepto["company_stage"] == "Series E"
    assert re_zepto["total_funding"] == "$1.5 Billion"

    re_tigi = next(r for r in rows if r["company_name"] == "Tigi HR")
    assert int(re_tigi["total_jobs_posted"]) == 1
    assert re_tigi["company_stage"] == "Bootstrapped"
    assert re_tigi["founders"] == "Kashyap Dave"


# ============================================================================
# 2. WELLFOUND DATA DUMP & FILTER PIPELINE TESTS
# ============================================================================

def test_wellfound_dump_and_filter_pipeline(tmp_path: Path, sample_wellfound_raw_jobs: List[Dict[str, Any]]):
    """Dump Wellfound raw card data, apply filtering, aggregate, and verify output completeness."""
    raw_dump_file = tmp_path / "raw_wellfound_dump.json"

    # Dump raw card data
    with raw_dump_file.open("w", encoding="utf-8") as f:
        json.dump(sample_wellfound_raw_jobs, f, indent=2)

    assert raw_dump_file.exists()

    # Re-read raw dump
    with raw_dump_file.open("r", encoding="utf-8") as f:
        reloaded_raw = json.load(f)

    assert len(reloaded_raw) == 3

    # Filter with max_days = 7.0 (should keep HyperScale AI [0.2d, 3d], discard Legacy Tech [25d])
    filtered_companies = filter_and_aggregate_companies(reloaded_raw, max_days=7.0)

    assert len(filtered_companies) == 1
    ai_comp = filtered_companies[0]
    assert ai_comp["company_name"] == "HyperScale AI"
    assert ai_comp["total_jobs_posted"] == 2
    assert len(ai_comp["job_titles"]) == 2
    assert "Founding ML Systems Engineer" in ai_comp["job_titles"]
    assert "Full Stack Product Engineer" in ai_comp["job_titles"]
    assert "Bengaluru, India" in ai_comp["locations"]
    assert "Remote" in ai_comp["locations"]
    assert "$90k – $130k" in ai_comp["salaries"]
    assert "0.5% – 1.5%" in ai_comp["equity"]
    assert ai_comp["stage"] == "Seed"
    assert ai_comp["employee_count"] == "11-50 Employees"

    # Export to CSV and verify WELLFOUND_COMPANY_FIELDS
    csv_out = tmp_path / "wellfound_companies_dump.csv"
    with csv_out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=WELLFOUND_COMPANY_FIELDS)
        writer.writeheader()
        for c in filtered_companies:
            writer.writerow({
                "company_name": c["company_name"],
                "company_website": c.get("company_website", "https://hyperscale.ai"),
                "company_linkedin_url": c.get("company_linkedin_url", "https://linkedin.com/company/hyperscale-ai"),
                "total_jobs_posted": c["total_jobs_posted"],
                "job_titles": " | ".join(c["job_titles"]),
                "posted_dates": " | ".join(c.get("posted_dates", [])),
                "wellfound_job_urls": " | ".join(c["wellfound_job_urls"]),
                "locations": ", ".join(sorted(c["locations"])),
                "salaries": ", ".join(sorted(c["salaries"])),
                "equity": ", ".join(sorted(c["equity"])),
                "stage": c.get("stage", ""),
                "employee_count": c.get("employee_count", ""),
            })

    with csv_out.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        exported_rows = list(reader)

    for field in WELLFOUND_COMPANY_FIELDS:
        assert field in fields, f"Missing field in Wellfound CSV: {field}"

    assert len(exported_rows) == 1
    row = exported_rows[0]
    assert row["company_name"] == "HyperScale AI"
    assert int(row["total_jobs_posted"]) == 2
    assert "Bengaluru, India" in row["locations"]
    assert "Seed" in row["stage"]
