"""Unit tests for naukri_scraper.lead_enricher (TDD: RED phase)."""

from __future__ import annotations

import csv
from unittest.mock import MagicMock, patch

from naukri_scraper.config import LEAD_FIELDS
from naukri_scraper.lead_enricher import (
    check_domain_mx_doh,
    clean_and_validate_email,
    crawl_contact_pages,
    enrich_companies_to_leads,
    extract_domain,
    generate_email_permutations,
    resolve_company_domain,
    save_leads_to_csv,
    tag_hiring_intent,
)


def test_resolve_company_domain():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"name": "TaskUs", "domain": "taskus.com"}]
    mock_client.get.return_value = mock_resp

    domain = resolve_company_domain("TaskUs Pvt Ltd", mock_client)
    assert domain == "taskus.com"

    # Empty company
    assert resolve_company_domain("", mock_client) == ""


def test_extract_domain():
    assert extract_domain("https://www.example.com/about?ref=naukri") == "example.com"
    assert extract_domain("http://tech.startup.in/") == "tech.startup.in"
    assert extract_domain("https://company.io") == "company.io"
    assert extract_domain("not-a-url") == ""
    assert extract_domain("") == ""


def test_clean_and_validate_email():
    # Valid emails for company
    assert clean_and_validate_email("contact@mycompany.com", "mycompany.com") == "contact@mycompany.com"
    assert clean_and_validate_email("john.doe+hr@mycompany.com", "mycompany.com") == "john.doe+hr@mycompany.com"

    # Reject placeholder/junk/tracker emails
    assert clean_and_validate_email("user@example.com", "mycompany.com") is None
    assert clean_and_validate_email("test@domain.com", "mycompany.com") is None
    assert clean_and_validate_email("support@sentry.io", "mycompany.com") is None
    assert clean_and_validate_email("logo@2x.png", "mycompany.com") is None
    assert clean_and_validate_email("invalid-email", "mycompany.com") is None
    assert clean_and_validate_email("wix@wixpress.com", "mycompany.com") is None


def test_check_domain_mx_doh():
    # 1. Google Workspace MX mock
    mock_google_resp = MagicMock()
    mock_google_resp.status_code = 200
    mock_google_resp.json.return_value = {
        "Status": 0,
        "Answer": [
            {"name": "testco.com", "type": 15, "data": "10 aspmx.l.google.com."},
            {"name": "testco.com", "type": 15, "data": "20 alt1.aspmx.l.google.com."},
        ],
    }

    mock_client = MagicMock()
    mock_client.get.return_value = mock_google_resp

    is_valid, provider, records = check_domain_mx_doh(mock_client, "testco.com")
    assert is_valid is True
    assert provider == "Google Workspace"
    assert len(records) == 2

    # 2. Microsoft 365 MX mock
    mock_m365_resp = MagicMock()
    mock_m365_resp.status_code = 200
    mock_m365_resp.json.return_value = {
        "Status": 0,
        "Answer": [
            {"name": "m365co.com", "type": 15, "data": "0 m365co-com.mail.protection.outlook.com."},
        ],
    }
    mock_client.get.return_value = mock_m365_resp
    is_valid_m365, provider_m365, _ = check_domain_mx_doh(mock_client, "m365co.com")
    assert is_valid_m365 is True
    assert provider_m365 == "Microsoft 365"

    # 3. No MX records (NXDOMAIN or empty Answer)
    mock_nx_resp = MagicMock()
    mock_nx_resp.status_code = 200
    mock_nx_resp.json.return_value = {"Status": 3}
    mock_client.get.return_value = mock_nx_resp
    is_valid_nx, provider_nx, records_nx = check_domain_mx_doh(mock_client, "nonexistent-domain.xyz")
    assert is_valid_nx is False
    assert provider_nx == "None"
    assert records_nx == []


def test_crawl_contact_pages():
    mock_client = MagicMock()

    def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if url.endswith("/contact") or url.endswith("/contact-us"):
            resp.text = '<html><body>Contact us at <a href="mailto:hello@startup.io">Mail us</a></body></html>'
        elif url.endswith("/privacy-policy") or url.endswith("/privacy"):
            resp.text = '<html><body>For GDPR, contact our DPO at dpo@startup.io.</body></html>'
        elif url.endswith("/.well-known/security.txt"):
            resp.text = "Contact: mailto:security@startup.io\nExpires: 2027-01-01"
        else:
            resp.text = '<html><body>Welcome to Startup. Footer: support@startup.io</body></html>'
        return resp

    mock_client.get.side_effect = mock_get

    emails, contact_url = crawl_contact_pages(mock_client, "https://startup.io")
    assert "hello@startup.io" in emails
    assert "dpo@startup.io" in emails
    assert "security@startup.io" in emails
    assert "support@startup.io" in emails
    assert contact_url != ""


def test_generate_email_permutations():
    # Single founder
    perms = generate_email_permutations("Rohan Patel", "startup.io")
    assert "rohan@startup.io" in perms
    assert "rohan.patel@startup.io" in perms
    assert "r.patel@startup.io" in perms

    # Multiple founders comma separated
    multi_perms = generate_email_permutations("Alice Smith, Bob Jones", "startup.io")
    assert "alice@startup.io" in multi_perms
    assert "bob@startup.io" in multi_perms
    assert "alice.smith@startup.io" in multi_perms

    # Empty/None
    assert generate_email_permutations("", "startup.io") == []
    assert generate_email_permutations("Solo", "") == []


def test_tag_hiring_intent():
    titles = [
        "Senior MLOps Engineer (LLM / PyTorch)",
        "DevOps Lead - AWS Kubernetes",
        "Frontend React Developer",
        "VP of Sales & Enterprise Growth",
    ]
    signals = tag_hiring_intent(titles)
    assert "AI & Machine Learning" in signals
    assert "Cloud & Infrastructure" in signals
    assert "Frontend & Product" in signals
    assert "Sales & GTM Growth" in signals


def test_enrich_companies_to_leads(tmp_path):
    mock_companies = [
        {
            "company_name": "Test Startup",
            "company_website": "https://teststartup.io",
            "founders": "Aarav Sharma",
            "headquarters": "Bengaluru",
            "company_stage": "Series A",
            "total_funding": "$5M",
            "total_jobs_posted": 3,
            "job_titles": "['ML Engineer', 'DevOps Specialist']",
        }
    ]

    # Mock DoH and page crawler inside enrich_companies_to_leads
    with patch("naukri_scraper.lead_enricher.check_domain_mx_doh") as mock_mx, \
         patch("naukri_scraper.lead_enricher.crawl_contact_pages") as mock_crawl:
        mock_mx.return_value = (True, "Google Workspace", ["aspmx.l.google.com"])
        mock_crawl.return_value = (["team@teststartup.io"], "https://teststartup.io/contact")

        leads = enrich_companies_to_leads(mock_companies, max_workers=1)

        assert len(leads) == 1
        lead = leads[0]
        assert lead["company_name"] == "Test Startup"
        assert lead["company_domain"] == "teststartup.io"
        assert lead["mx_verified"] is True
        assert lead["mx_provider"] == "Google Workspace"
        assert "team@teststartup.io" in lead["emails_found"]
        assert "aarav@teststartup.io" in lead["lead_email_candidates"]
        assert "AI & Machine Learning" in lead["hiring_intent_signals"]

        # Verify saving to CSV
        csv_file = tmp_path / "leads_test.csv"
        saved_path = save_leads_to_csv(leads, str(csv_file))
        assert saved_path.exists()

        with saved_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["company_name"] == "Test Startup"
            for field in LEAD_FIELDS:
                assert field in rows[0]
