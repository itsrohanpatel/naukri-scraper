"""LinkedIn job scraper — Direct Guest API and Playwright fallback with multi-tier company enrichment."""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
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


def _run_coroutine_safely(coro: Any) -> Any:
    """Execute coroutine safely whether an asyncio loop is already running or not."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()


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
        kw_str = " ".join(keywords) if keywords else ""
        primary_loc = location or "India"
        tpr_seconds = self.get_f_tpr_seconds(days=days, hours=hours)

        max_allowed_age_days: Optional[float] = None
        if hours is not None:
            max_allowed_age_days = hours / 24.0
        elif days is not None:
            max_allowed_age_days = float(days)

        jobs: List[Dict[str, Any]] = []
        seen_urls = set()

        # Build list of locations to search (if target > 500 and location is India, fallback to top tech cities when offset limit is reached)
        locations_to_query = [primary_loc]
        if max_jobs > 500 and primary_loc.strip().lower() in ["india", ""]:
            locations_to_query.extend([
                "Bengaluru, Karnataka, India",
                "Mumbai, Maharashtra, India",
                "Delhi, India",
                "Hyderabad, Telangana, India",
                "Pune, Maharashtra, India",
                "Chennai, Tamil Nadu, India",
                "Gurgaon, Haryana, India",
                "Noida, Uttar Pradesh, India",
            ])

        logger.info(
            "Querying LinkedIn Guest API: keywords='%s', location='%s', f_TPR=%s, target_max=%d",
            kw_str or "(None/All Roles)",
            primary_loc,
            tpr_seconds,
            max_jobs,
        )

        with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
            for loc in locations_to_query:
                if len(jobs) >= max_jobs:
                    break

                start = 0
                consecutive_empty = 0

                while len(jobs) < max_jobs and start <= 980:
                    params: Dict[str, Any] = {
                        "location": loc,
                        "start": start,
                    }
                    if kw_str:
                        params["keywords"] = kw_str
                    if tpr_seconds:
                        params["f_TPR"] = f"r{tpr_seconds}"

                    resp = None
                    for attempt in range(4):
                        try:
                            resp = client.get(LINKEDIN_GUEST_API_URL, params=params)
                            if resp.status_code == 429:
                                backoff = 4.0 * (attempt + 1)
                                logger.warning("LinkedIn rate-limited (429) at start=%d. Sleeping %.1fs before retry...", start, backoff)
                                time.sleep(backoff)
                                continue
                            break
                        except Exception as exc:
                            logger.debug("Request exception on attempt %d: %s", attempt, exc)
                            time.sleep(2.0)

                    if not resp or resp.status_code != 200:
                        logger.debug("LinkedIn Guest API non-200 (%s) for '%s' at start=%d", getattr(resp, "status_code", "None"), loc, start)
                        break

                    soup = BeautifulSoup(resp.text, "html.parser")
                    card_elems = soup.find_all("li")
                    if not card_elems:
                        consecutive_empty += 1
                        if consecutive_empty >= 3:
                            break
                        start += 10
                        continue

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
                        consecutive_empty += 1
                        if consecutive_empty >= 4:
                            break
                    else:
                        consecutive_empty = 0
                        if len(jobs) % 50 < 10 or len(jobs) == max_jobs:
                            print(f"  [+] Progress: {len(jobs):,}/{max_jobs:,} LinkedIn jobs collected (Location: {loc.split(',')[0]})...", flush=True)

                    start += max(len(card_elems), 10)
                    time.sleep(random.uniform(0.7, 1.2))  # Respectful jittered delay to prevent 429s

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
            # Mask navigator.webdriver for anti-bot evasion
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
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
            if url:
                search_url = url
            else:
                kw_part = f"keywords={urllib.parse.quote_plus(' '.join(keywords))}&" if keywords else ""
                loc_part = f"location={urllib.parse.quote_plus(location or 'India')}"
                search_url = f"https://www.linkedin.com/jobs/search?{kw_part}{loc_part}"
            jobs = _run_coroutine_safely(self.scrape_browser_async(search_url, max_jobs=max_jobs, days=days, hours=hours))
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
        """Enrich company domains and metadata using Inc42 and cached lookups."""
        from .browser_scraper import search_company_website_ddgs_sync
        from .inc42_scraper import batch_enrich_inc42

        # 1. Collect unique company names
        unique_companies = list(set(j["company"] for j in jobs if j.get("company")))
        if not unique_companies:
            return

        # 2. Run Inc42 corporate & startup enrichment
        try:
            inc42_raw = _run_coroutine_safely(batch_enrich_inc42(unique_companies))
            inc42_results = {k.lower(): v for k, v in inc42_raw.items()}
        except Exception as exc:
            logger.debug("Inc42 enrichment error: %s", exc)
            inc42_results = {}

        # 3. Cache website resolutions per company
        website_cache: Dict[str, str] = {}
        for cname_lower, info in inc42_results.items():
            if info.get("company_website"):
                website_cache[cname_lower] = info["company_website"]

        # Only use DDGS fallback for up to 25 remaining unique companies to prevent DDG rate limits
        missing_comps = [c for c in unique_companies if c.lower() not in website_cache]
        for c in missing_comps[:25]:
            try:
                site = search_company_website_ddgs_sync(c)
                if site:
                    website_cache[c.lower()] = site
            except Exception:
                pass


        # 4. Apply results to jobs
        for j in jobs:
            cname = j.get("company", "").strip()
            if not cname:
                continue
            c_key = cname.lower()

            info = inc42_results.get(c_key, {})
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

            if not j.get("company_website") and c_key in website_cache:
                j["company_website"] = website_cache[c_key]
