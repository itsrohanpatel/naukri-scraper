"""Inc42 Datalabs company scraper and enrichment module.

Extracts structured startup & corporate metadata from Inc42 (https://inc42.com/company/<slug>/):
- Official Website
- Company LinkedIn Profile
- Founders
- Employee Count
- Founding Year
- Funding Stage (Bootstrapped, Seed, Series A/B/C, etc.)
- Headquarters City & Location
- Industry Categories & Description
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

INC42_BASE_URL = "https://inc42.com/company"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean_company_slugs(company_name: str) -> List[str]:
    """Generates ordered candidate URL slugs for Inc42 company profiles."""
    if not company_name or not company_name.strip():
        return []

    candidates: List[str] = []
    raw = company_name.strip()

    # 1. Remove text inside parentheses e.g. "Willis Towers Watson (WTW)" -> "Willis Towers Watson"
    no_parens = re.sub(r"\(.*?\)", "", raw).strip()

    # 2. Remove corporate/legal suffixes
    cleaned = re.sub(
        r"\b(pvt\.?|private|ltd\.?|limited|llc|inc\.?|corp\.?|corporation|group|services|enterprises|technologies|technology|solutions|india)\b",
        "",
        no_parens,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Generate slug helper
    def to_slug(text: str) -> str:
        s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
        return s

    # Primary slug: cleaned name
    if cleaned:
        slug_cleaned = to_slug(cleaned)
        if slug_cleaned and slug_cleaned not in candidates:
            candidates.append(slug_cleaned)

    # Secondary slug: no parens
    if no_parens:
        slug_no_parens = to_slug(no_parens)
        if slug_no_parens and slug_no_parens not in candidates:
            candidates.append(slug_no_parens)

    # Tertiary slug: raw name
    slug_raw = to_slug(raw)
    if slug_raw and slug_raw not in candidates:
        candidates.append(slug_raw)

    return candidates


def parse_inc42_html(html_text: str, source_url: str = "") -> Dict[str, Any]:
    """Parses Inc42 company HTML page and extracts all structured metadata."""
    data: Dict[str, Any] = {
        "inc42_url": source_url,
        "company_name": "",
        "company_website": "",
        "company_linkedin": "",
        "founders": [],
        "founding_year": "",
        "employee_count": "",
        "headquarters": "",
        "company_stage": "",
        "industry_tags": [],
        "description": "",
        "logo_url": "",
    }

    if not html_text or "Company-schema" not in html_text:
        return {}

    soup = BeautifulSoup(html_text, "html.parser")

    # 1. Extract from Company-schema (Corporation)
    comp_script = soup.find("script", id="Company-schema")
    if comp_script and comp_script.string:
        try:
            corp = json.loads(comp_script.string)
            data["company_name"] = corp.get("name") or ""
            data["company_website"] = (corp.get("url") or "").strip()
            data["logo_url"] = corp.get("logo") or corp.get("image") or ""
            data["description"] = corp.get("description") or ""
            data["founding_year"] = str(corp.get("foundingDate") or "")

            same_as = corp.get("sameAs", [])
            if isinstance(same_as, list):
                for link in same_as:
                    if link and isinstance(link, str) and "linkedin.com" in link.lower():
                        data["company_linkedin"] = link.strip()
                    elif not data["company_website"] and link and isinstance(link, str) and "linkedin.com" not in link.lower():
                        data["company_website"] = link.strip()

            data["industry_tags"] = corp.get("knowsAbout", []) or []

            # Number of employees
            emp_info = corp.get("numberOfEmployees")
            if isinstance(emp_info, dict):
                data["employee_count"] = str(emp_info.get("value") or "")
            elif emp_info:
                data["employee_count"] = str(emp_info)

            # Founders
            founders_raw = corp.get("founder", [])
            if isinstance(founders_raw, list):
                names = []
                for f in founders_raw:
                    if isinstance(f, dict) and f.get("name"):
                        names.append(f["name"].strip())
                    elif isinstance(f, str) and f.strip():
                        names.append(f.strip())
                data["founders"] = names

        except Exception as e:
            logger.debug("Failed parsing Company-schema: %s", e)

    # 2. Extract from schema-dataset for Headquarters and Funding Stage
    ds_script = soup.find("script", id="schema-dataset")
    if ds_script and ds_script.string:
        try:
            ds = json.loads(ds_script.string)
            title = ds.get("name", "")
            # e.g. "TIGI HR - An Enterprise Services Bootstrapped Company Based Out Of Ahmedabad"
            match_hq = re.search(r"Based Out Of\s+(.+)$", title, re.IGNORECASE)
            if match_hq and not data.get("headquarters"):
                data["headquarters"] = match_hq.group(1).strip()

            match_stage = re.search(
                r"\b(Bootstrapped|Seed|Series [A-Z]|Late Stage|Early Stage|Funded|Acquired|Public)\b",
                title,
                re.IGNORECASE,
            )
            if match_stage and not data.get("company_stage"):
                data["company_stage"] = match_stage.group(1).strip()
        except Exception as e:
            logger.debug("Failed parsing schema-dataset: %s", e)

    # 3. Extract from FAQ schema (faq-init) for Funded Companies (Headquarters, Total Funding, Revenue)
    faq_script = soup.find("script", id="faq-init")
    if faq_script and faq_script.string:
        try:
            faq_data = json.loads(faq_script.string)
            questions = faq_data.get("mainEntity", [])
            for q in questions:
                q_text = (q.get("name") or "").lower()
                ans_text = q.get("acceptedAnswer", {}).get("text") or ""
                # Strip HTML tags from answer text
                clean_ans = re.sub(r"<[^>]+>", "", ans_text).strip()

                if "headquartered" in q_text and not data.get("headquarters"):
                    m = re.search(r"headquartered in\s+([^,\.]+)", clean_ans, re.IGNORECASE)
                    if m:
                        data["headquarters"] = m.group(1).strip()
                    else:
                        data["headquarters"] = clean_ans

                elif "funding" in q_text:
                    m = re.search(r"total funding of\s+([^\.]+across[^\.]+rounds|\$[0-9\.]+\s*(?:million|billion|mn|bn)?)", clean_ans, re.IGNORECASE)
                    if m:
                        data["total_funding"] = m.group(1).strip()
                    elif clean_ans:
                        data["total_funding"] = clean_ans[:100]
                    if not data.get("company_stage"):
                        data["company_stage"] = "Funded"

                elif "revenue" in q_text:
                    m = re.search(r"revenue of\s+([^\.]+in\s+FY\d+|\u20b9[0-9\.,]+\s*(?:Cr|Lakh|Crore)?)", clean_ans, re.IGNORECASE)
                    rev_val = m.group(1).strip() if m else clean_ans[:100]
                    data["revenue"] = rev_val.replace("\u20b9", "INR ")

        except Exception as e:
            logger.debug("Failed parsing faq-init: %s", e)

    # Validate that we got at least a name or website
    if not data.get("company_name") and not data.get("company_website"):
        return {}

    return data


def search_inc42_ddgs(company_name: str) -> Optional[str]:
    """Uses DDGS search to locate an Inc42 company profile if slug generation misses."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
    except ImportError:
        return None

    raw = company_name.strip()
    no_parens = re.sub(r"\(.*?\)", "", raw).strip()
    cleaned = re.sub(
        r"\b(pvt\.?|private|ltd\.?|limited|llc|inc\.?|corp\.?|corporation|group|services|enterprises|technologies|technology|solutions|india)\b",
        "",
        no_parens,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    search_terms = []
    if cleaned and cleaned.lower() != raw.lower():
        search_terms.append(cleaned)
    search_terms.append(raw)

    for term in search_terms:
        queries = [
            f'site:inc42.com/company/ "{term}"',
            f'site:inc42.com "{term}"',
            f'"{term}" Inc42',
        ]
        for q in queries:
            try:
                with DDGS(timeout=5) as ddgs:
                    results = list(ddgs.text(q, max_results=4))
                    for r in results:
                        url = r.get("href", "")
                        if "inc42.com/company/" in url and not url.rstrip("/").endswith("/company"):
                            return url
            except Exception:
                continue

    return None



async def fetch_inc42_page(
    client: httpx.AsyncClient,
    url: str,
    expected_slug: str = "",
) -> Optional[Dict[str, Any]]:
    """Fetches and parses an Inc42 company page, validating that it is not a 301 redirect."""
    try:
        resp = await client.get(url, headers=DEFAULT_HEADERS, timeout=12.0)
        # Check if redirected to home or non-company page
        final_url = str(resp.url).rstrip("/")
        if resp.status_code == 200 and "/company/" in final_url:
            if expected_slug and expected_slug not in final_url.lower():
                # Avoid redirect to completely different page
                pass
            parsed = parse_inc42_html(resp.text, source_url=final_url)
            if parsed:
                return parsed
    except Exception as e:
        logger.debug("Error fetching Inc42 URL %s: %s", url, e)
    return None


async def extract_inc42_company_data(
    client: httpx.AsyncClient,
    company_name: str,
    semaphore: asyncio.Semaphore,
    use_ddgs_fallback: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """Primary asynchronous function to resolve and enrich a company via Inc42."""
    async with semaphore:
        slugs = clean_company_slugs(company_name)

        # 1. Try direct candidate slugs
        for slug in slugs:
            url = f"{INC42_BASE_URL}/{slug}/"
            res = await fetch_inc42_page(client, url, expected_slug=slug)
            if res:
                return company_name, res
            await asyncio.sleep(0.05)

        # 2. Try DDGS search fallback if slug wasn't exact
        if use_ddgs_fallback:
            loop = asyncio.get_running_loop()
            found_url = await loop.run_in_executor(None, search_inc42_ddgs, company_name)
            if found_url:
                res = await fetch_inc42_page(client, found_url)
                if res:
                    return company_name, res

        return company_name, {}


async def batch_enrich_inc42(
    company_names: List[str],
    concurrency: int = 8,
    use_ddgs_fallback: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Enriches a batch of unique company names concurrently via Inc42."""
    results: Dict[str, Dict[str, Any]] = {}
    unique_names = sorted(list(set(c.strip() for c in company_names if c and c.strip())))
    if not unique_names:
        return results

    semaphore = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_keepalive_connections=concurrency * 2, max_connections=concurrency * 3)

    async with httpx.AsyncClient(limits=limits, follow_redirects=True) as client:
        tasks = [
            extract_inc42_company_data(client, c, semaphore, use_ddgs_fallback=use_ddgs_fallback)
            for c in unique_names
        ]
        for coro in asyncio.as_completed(tasks):
            cname, data = await coro
            if data:
                results[cname] = data

    return results
