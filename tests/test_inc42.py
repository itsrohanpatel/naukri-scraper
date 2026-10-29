"""Unit tests & CLI diagnostic tool for Inc42 scraper module."""

from __future__ import annotations

import argparse
import asyncio
import json

from naukri_scraper.inc42_scraper import (
    clean_company_slugs,
    parse_inc42_html,
    extract_inc42_company_data,
)


def test_clean_company_slugs():
    assert clean_company_slugs("") == []
    assert "tigi-hr" in clean_company_slugs("Tigi HR")
    assert "tigi-hr" in clean_company_slugs("Tigi HR Pvt. Ltd.")
    assert "willis-towers-watson" in clean_company_slugs("Willis Towers Watson (WTW)")
    assert "zepto" in clean_company_slugs("Zepto India Technologies Private Limited")


def test_parse_inc42_html_mock():
    mock_html = """
    <html>
    <head>
        <script id="Company-schema" type="application/ld+json">
        {
            "@type": "Corporation",
            "name": "Zepto",
            "url": "https://www.zeptonow.com",
            "foundingDate": "2021",
            "sameAs": [
                "https://www.linkedin.com/company/zepto-consumer/"
            ],
            "knowsAbout": ["Quick Commerce", "E-Commerce"],
            "numberOfEmployees": "1000+",
            "founder": [
                {"name": "Aadit Palicha"},
                {"name": "Kaivalya Vohra"}
            ]
        }
        </script>
        <script id="schema-dataset" type="application/ld+json">
        {
            "name": "Zepto - A Quick Commerce Series E Company Based Out Of Mumbai"
        }
        </script>
        <script id="faq-init" type="application/ld+json">
        {
            "mainEntity": [
                {
                    "name": "What is the total funding of Zepto?",
                    "acceptedAnswer": {"text": "Zepto has raised a total funding of $1.5 Billion across 8 rounds."}
                },
                {
                    "name": "What is the revenue of Zepto?",
                    "acceptedAnswer": {"text": "Zepto reported revenue of INR 2000 Cr in FY24."}
                }
            ]
        }
        </script>
    </head>
    <body></body>
    </html>
    """
    result = parse_inc42_html(mock_html, source_url="https://inc42.com/company/zepto/")
    assert result["company_name"] == "Zepto"
    assert result["company_website"] == "https://www.zeptonow.com"
    assert result["company_linkedin"] == "https://www.linkedin.com/company/zepto-consumer/"
    assert result["founding_year"] == "2021"
    assert "Aadit Palicha" in result["founders"]
    assert "Kaivalya Vohra" in result["founders"]
    assert result["headquarters"] == "Mumbai"
    assert "Series E" in result["company_stage"]
    assert "$1.5 Billion" in result["total_funding"]
    assert "INR 2000 Cr" in result["revenue"]


# =====================================================================
# CLI Diagnostic Runner (Used by GitHub Actions & Local testing)
# =====================================================================

def main(argv=None):
    parser = argparse.ArgumentParser(description="Test Inc42 company data extraction.")
    parser.add_argument("--company", type=str, help="Company name to test (e.g. 'Tigi HR')")
    parser.add_argument("--url", type=str, help="Direct Inc42 URL to test")
    parser.add_argument("--test-suite", action="store_true", help="Run benchmark suite")
    parser.add_argument("--no-ddgs", action="store_true", help="Disable DDGS fallback")
    args = parser.parse_args(argv)

    company = args.company or "Tigi HR"

    print(f"[*] Testing Inc42 extraction for company: {company}")

    async def _run():
        import httpx
        sem = asyncio.Semaphore(1)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            _, data = await extract_inc42_company_data(client, company, sem, use_ddgs_fallback=not args.no_ddgs)
            print(f"[+] Result: {json.dumps(data, indent=2)}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
