"""Unit tests & CLI diagnostic tool for AmbitionBox extraction."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from typing import Any, Dict

import pytest



def parse_ambitionbox_html(html_text: str) -> Dict[str, Any]:
    """Extracts structured AmbitionBox company metadata from HTML (__NEXT_DATA__)."""
    extracted: Dict[str, Any] = {}
    if not html_text:
        return extracted

    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            props = d.get("props", {}).get("pageProps", {}) or {}
            meta = props.get("companyMetaInformation", {}) or {}
            header = props.get("companyHeaderData", {}) or {}

            extracted = {
                "Company Name": header.get("name") or header.get("companyName") or "",
                "Official Website": (meta.get("website") or header.get("website") or "").strip(),
                "Rating": str(header.get("rating") or header.get("companyRating") or ""),
                "Reviews Count": str(header.get("reviewsCount") or header.get("totalReviews") or ""),
                "Industry": meta.get("industry") or header.get("industry") or "",
                "Headquarters": meta.get("headquarters") or header.get("hq") or "",
            }
        except Exception:
            pass

    if not extracted.get("Official Website"):
        web_m = re.search(r'"website"\s*:\s*"(https?://[^"]+)"', html_text)
        if web_m:
            extracted["Official Website"] = web_m.group(1).replace("\\/", "").strip()

    return extracted


def test_parse_ambitionbox_html():
    mock_html = """
    <html>
    <head>
        <script id="__NEXT_DATA__" type="application/json">
        {
            "props": {
                "pageProps": {
                    "companyHeaderData": {
                        "name": "Tata Consultancy Services",
                        "rating": "3.8",
                        "reviewsCount": "75000"
                    },
                    "companyMetaInformation": {
                        "website": "https://www.tcs.com",
                        "industry": "IT Services & Consulting",
                        "headquarters": "Mumbai, Maharashtra"
                    }
                }
            }
        }
        </script>
    </head>
    <body></body>
    </html>
    """
    result = parse_ambitionbox_html(mock_html)
    assert result["Company Name"] == "Tata Consultancy Services"
    assert result["Official Website"] == "https://www.tcs.com"
    assert result["Rating"] == "3.8"
    assert result["Reviews Count"] == "75000"
    assert result["Headquarters"] == "Mumbai, Maharashtra"


# =====================================================================
# CLI Diagnostic Runner (Used by GitHub Actions & Local testing)
# =====================================================================

async def run_ambitionbox_live(url: str):
    from playwright.async_api import async_playwright
    print(f"[*] Testing AmbitionBox URL: {url}")
    async with async_playwright() as p:
        browser = None
        for channel in ["msedge", "chrome", None]:
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    channel=channel,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )
                break
            except Exception:
                continue

        if not browser:
            print("[!] Could not launch Chromium/Edge browser.")
            return

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            content = await page.content()
            data = parse_ambitionbox_html(content)
            print(f"[+] Result: {json.dumps(data, indent=2)}")
        except Exception as exc:
            print(f"[!] Error fetching AmbitionBox page: {exc}")
        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_dynamic_extract_clearbit_non_dict_elements():
    """Verify that Clearbit parser handles unexpected non-dict items in list without raising AttributeError."""
    from unittest.mock import AsyncMock, MagicMock
    from naukri_scraper.browser_scraper import dynamic_extract_clearbit

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = ["unexpected_string_element"]  # non-dict inside list
    mock_client.get = AsyncMock(return_value=mock_resp)

    sem = asyncio.Semaphore(1)
    name, domain = await dynamic_extract_clearbit(mock_client, "TestCo", sem)
    assert name == "TestCo"
    assert domain == ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Test AmbitionBox company extraction")
    parser.add_argument(
        "--url",
        default="https://www.ambitionbox.com/overview/tcs-overview",
        help="AmbitionBox overview or review URL",
    )
    args = parser.parse_args(argv)
    clean_url = args.url.strip()
    if "/reviews/" in clean_url:
        clean_url = re.sub(r"/reviews/([a-zA-Z0-9_-]+)-reviews", r"/overview/\1-overview", clean_url.split("?")[0])
    asyncio.run(run_ambitionbox_live(clean_url))


if __name__ == "__main__":
    main()

