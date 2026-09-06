"""LinkedIn job scraper — Direct Guest API and Playwright fallback with multi-tier company enrichment."""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup, Tag


logger = logging.getLogger(__name__)

LINKEDIN_GUEST_API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


def parse_linkedin_posted_age_days(text: str) -> float:
    """Calculate job posting age in days from strings like '2 hours ago', '3 days ago', '1 week ago'."""
    if not text:
        return 999.0
    clean = text.lower().strip()
    if "just now" in clean or "today" in clean:
        return 0.0
    if "yesterday" in clean:
        return 1.0

    m_h = re.search(r"(\d+)\s*(?:hours?|hrs?|h)\s*ago", clean)
    if m_h:
        return float(m_h.group(1)) / 24.0

    m_m = re.search(r"(\d+)\s*(?:mins?|minutes?|m)\s*ago", clean)
    if m_m:
        return float(m_m.group(1)) / 1440.0

    m_d = re.search(r"(\d+)\s*(?:days?|d)\s*ago", clean)
    if m_d:
        return float(m_d.group(1))

    m_w = re.search(r"(\d+)\s*(?:weeks?|w)\s*ago", clean)
    if m_w:
        return float(m_w.group(1)) * 7.0

    m_mo = re.search(r"(\d+)\s*(?:months?|mo)\s*ago", clean)
    if m_mo:
        return float(m_mo.group(1)) * 30.0

    return 999.0


def parse_linkedin_card_html(card: Tag) -> Optional[Dict[str, Any]]:
    """Extract structured job data from a LinkedIn job card HTML element."""
    if not card:
        return None

    # Title & Link
    title_elem = card.find("h3", class_="base-search-card__title")
    link_elem = card.find("a", class_="base-card__full-link")
    if not title_elem and not link_elem:
        # Fallback query
        title_elem = card.find("a", class_="job-card-list__title")
        link_elem = title_elem

    title = title_elem.get_text(strip=True) if title_elem else ""
    raw_url = link_elem["href"].strip() if link_elem and link_elem.has_attr("href") else ""
    # Strip tracking query parameters from job URL
    url = urllib.parse.urljoin("https://www.linkedin.com", raw_url.split("?")[0]) if raw_url else ""

    # Extract Job ID
    job_id = ""
    m_id = re.search(r"-(\d+)$", url)
    if m_id:
        job_id = m_id.group(1)

    # Company & Company LinkedIn
    comp_elem = card.find("h4", class_="base-search-card__subtitle")
    company = ""
    company_linkedin = ""
    if comp_elem:
        comp_link = comp_elem.find("a")
        if comp_link and comp_link.has_attr("href"):
            company = comp_link.get_text(strip=True)
            company_linkedin = comp_link["href"].split("?")[0].strip()
        else:
            company = comp_elem.get_text(strip=True)

    # Location
    loc_elem = card.find("span", class_="job-search-card__location")
    location = loc_elem.get_text(strip=True) if loc_elem else "India"

    # Date
    time_elem = card.find("time")
    posted_date = ""
    age_text = ""
    age_days = 999.0
    if time_elem:
        if time_elem.has_attr("datetime"):
            posted_date = time_elem["datetime"].strip()
        age_text = time_elem.get_text(strip=True)
        age_days = parse_linkedin_posted_age_days(age_text)

    if not title or not company:
        return None

    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "company_website": "",
        "company_linkedin": company_linkedin,
        "location": location,
        "experience_text": "Not specified",
        "salary": "Not disclosed",
        "skills": "",
        "job_description": "",
        "company_rating": "",
        "company_reviews_count": "",
        "ambition_box_url": "",
        "vacancies": "",
        "freshness": age_text,
        "posted_date": posted_date,
        "age_days": age_days,
        "min_experience": 0,
        "max_experience": 99,
        "url": url,
        "source": "linkedin",
        "headquarters": "",
        "founders": "",
        "founding_year": "",
        "company_stage": "",
        "total_funding": "",
        "revenue": "",
    }


class LinkedInScraper:
    """High-performance scraper for LinkedIn job listings with date limits & company enrichment."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def get_f_tpr_seconds(
        self, days: Optional[int] = None, hours: Optional[int] = None
    ) -> Optional[int]:
        """Convert days or hours into LinkedIn's f_TPR seconds parameter."""
        if hours is not None:
            return hours * 3600
        if days is not None:
            return days * 86400
        return None

    def scrape_guest_api(
        self,
        keywords: Optional[List[str]] = None,
        location: Optional[str] = None,
        max_jobs: int = 50,
        days: Optional[int] = None,
        hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape LinkedIn jobs via the fast public Guest API without browser overhead."""
        kw_str = " ".join(keywords) if keywords else "Software Engineer"
        loc_str = location or "India"
        tpr_seconds = self.get_f_tpr_seconds(days=days, hours=hours)

        max_allowed_age_days: Optional[float] = None
        if hours is not None:
            max_allowed_age_days = hours / 24.0
        elif days is not None:
            max_allowed_age_days = float(days)

        jobs: List[Dict[str, Any]] = []
        seen_urls = set()
        start = 0

        logger.info(
            "Querying LinkedIn Guest API: keywords='%s', location='%s', f_TPR=%s, target_max=%d",
            kw_str,
            loc_str,
            tpr_seconds,
            max_jobs,
        )

        with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
            while len(jobs) < max_jobs:
                params: Dict[str, Any] = {
                    "keywords": kw_str,
                    "location": loc_str,
                    "start": start,
                }
                if tpr_seconds:
                    params["f_TPR"] = f"r{tpr_seconds}"

                try:
                    resp = client.get(LINKEDIN_GUEST_API_URL, params=params)
                    if resp.status_code != 200:
                        logger.warning("LinkedIn Guest API returned status %d at start=%d", resp.status_code, start)
                        break

                    soup = BeautifulSoup(resp.text, "html.parser")
                    card_elems = soup.find_all("li")
                    if not card_elems:
                        logger.info("No more job cards returned from LinkedIn at start=%d", start)
                        break

                    added_in_batch = 0
                    for card in card_elems:
                        job = parse_linkedin_card_html(card)
                        if not job or not job["url"] or job["url"] in seen_urls:
                            continue

                        # Client-side date limit verification (Layer 2)
                        if max_allowed_age_days is not None:
                            if job["age_days"] > max_allowed_age_days + 0.1:
                                continue

                        seen_urls.add(job["url"])
                        jobs.append(job)
                        added_in_batch += 1

                        if len(jobs) >= max_jobs:
                            break

                    if added_in_batch == 0:
                        break

                    start += 25
                except Exception as exc:
                    logger.error("Error fetching LinkedIn Guest API batch: %s", exc)
                    break

        return jobs

    async def scrape_browser_async(
        self,
        url: str,
        max_jobs: int = 50,
        days: Optional[int] = None,
        hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape LinkedIn jobs via Playwright browser automation with infinite scroll."""
        from playwright.async_api import async_playwright

        max_allowed_age_days: Optional[float] = None
        if hours is not None:
            max_allowed_age_days = hours / 24.0
        elif days is not None:
            max_allowed_age_days = float(days)

        jobs: List[Dict[str, Any]] = []
        seen_urls = set()

        async with async_playwright() as p:
            browser = None
            for channel in ["msedge", "chrome", None]:
                try:
                    if channel:
                        browser = await p.chromium.launch(channel=channel, headless=True)
                    else:
                        browser = await p.chromium.launch(headless=True)
                    break
                except Exception:
                    continue

            if not browser:
                logger.error("Could not launch Playwright browser (Edge, Chrome, or Chromium).")
                return []

            context = await browser.new_context(
                user_agent=self.headers["User-Agent"],
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            try:
                # Add date filter param to URL if not already present
                target_url = url
                tpr_seconds = self.get_f_tpr_seconds(days=days, hours=hours)
                if tpr_seconds and "f_TPR=" not in target_url:
                    sep = "&" if "?" in target_url else "?"
                    target_url = f"{target_url}{sep}f_TPR=r{tpr_seconds}"

                logger.info("Navigating Playwright to: %s", target_url)
                await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2.5)

                # Scroll down to load jobs
                for _ in range(10):
                    cards = await page.locator("ul.jobs-search__results-list li, .base-card").all()
                    if len(cards) >= max_jobs:
                        break
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1.2)
                    # Check if 'See more jobs' button is visible and click it
                    btn = page.locator("button.infinite-scroller__show-more-button")
                    if await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(1.0)

                html_content = await page.content()
                soup = BeautifulSoup(html_content, "html.parser")
                card_elems = soup.find_all("li", class_=re.compile(r"(base-card|job-search-card)"))

                for card in card_elems:
                    job = parse_linkedin_card_html(card)
                    if not job or not job["url"] or job["url"] in seen_urls:
                        continue
                    if max_allowed_age_days is not None and job["age_days"] > max_allowed_age_days + 0.1:
                        continue

                    seen_urls.add(job["url"])
                    jobs.append(job)
                    if len(jobs) >= max_jobs:
                        break

            except Exception as exc:
                logger.error("Playwright scraping failed: %s", exc)
            finally:
                await browser.close()

        return jobs

    def scrape(
        self,
        keywords: Optional[List[str]] = None,
        location: Optional[str] = None,
        url: Optional[str] = None,
        max_jobs: int = 50,
        days: Optional[int] = None,
        hours: Optional[int] = None,
        use_browser: bool = False,
    ) -> List[Dict[str, Any]]:
        """Main scraping entrypoint dispatching between Guest API and Playwright browser."""
        if use_browser or url:
            search_url = url or (
                f"https://www.linkedin.com/jobs/search?keywords={urllib.parse.quote_plus(' '.join(keywords or ['Software Engineer']))}&location={urllib.parse.quote_plus(location or 'India')}"
            )
            jobs = asyncio.run(self.scrape_browser_async(search_url, max_jobs=max_jobs, days=days, hours=hours))
        else:
            jobs = self.scrape_guest_api(
                keywords=keywords,
                location=location,
                max_jobs=max_jobs,
                days=days,
                hours=hours,
            )

        logger.info("Scraped %d jobs from LinkedIn. Running company enrichment...", len(jobs))
        self._enrich_jobs(jobs)
        return jobs

    def _enrich_jobs(self, jobs: List[Dict[str, Any]]) -> None:
        """Enrich company domains and metadata using Inc42, Clearbit, and DuckDuckGo."""
        from .browser_scraper import search_company_website_ddgs_sync
        from .inc42_scraper import batch_enrich_inc42

        # 1. Collect unique company names
        unique_companies = list(set(j["company"] for j in jobs if j.get("company")))
        if not unique_companies:
            return

        # 2. Run Inc42 corporate & startup enrichment
        try:
            inc42_raw = asyncio.run(batch_enrich_inc42(unique_companies))
            inc42_results = {k.lower(): v for k, v in inc42_raw.items()}
        except Exception as exc:
            logger.debug("Inc42 enrichment error: %s", exc)
            inc42_results = {}

        # 3. Apply results & fall back to Clearbit/DDGS
        for j in jobs:
            cname = j.get("company", "").strip()
            if not cname:
                continue

            info = inc42_results.get(cname.lower(), {})
            if info:
                j["company_website"] = info.get("company_website", "")
                if not j.get("company_linkedin") and info.get("company_linkedin"):
                    j["company_linkedin"] = info.get("company_linkedin", "")
                j["headquarters"] = info.get("headquarters", "")
                j["founders"] = ", ".join(info.get("founders", [])) if isinstance(info.get("founders"), list) else ""
                j["founding_year"] = info.get("founding_year", "")
                j["company_stage"] = info.get("company_stage", "")
                j["total_funding"] = info.get("total_funding", "")
                j["revenue"] = info.get("revenue", "")

            # If still no website, fallback to DDGS
            if not j.get("company_website"):
                try:
                    site = search_company_website_ddgs_sync(cname)
                    if site:
                        j["company_website"] = site
                except Exception:
                    pass
