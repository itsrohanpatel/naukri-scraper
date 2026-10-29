"""Automated B2B Lead Generation and Verification Engine.

Zero external dependencies: uses Python stdlib + httpx, beautifulsoup4.
100% runnable in GitHub Actions via pure HTTPS (DoH MX check + targeted crawl).
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .config import LEAD_FIELDS
from .exporter import save_leads_to_csv, save_leads_to_json

logger = logging.getLogger(__name__)

# RFC 5322 simplified email matching pattern
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")

# Discard common file extensions or image noise accidentally matched as emails
INVALID_EMAIL_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff",
    ".css", ".js", ".map", ".woff", ".woff2", ".ttf", ".eot",
)

# Reject generic dummy/placeholder domains
JUNK_DOMAINS = {
    "example.com", "example.org", "example.net",
    "domain.com", "yourdomain.com", "company.com",
    "email.com", "test.com", "mysite.com",
    "sentry.io", "wixpress.com", "github.com",
}

# Targeted public pages likely to contain contact & team emails
TARGET_CRAWL_PATHS = [
    "/",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/team",
    "/privacy-policy",
    "/privacy",
    "/.well-known/security.txt",
]

# Hiring intent keyword triggers
HIRING_INTENT_MAP = {
    "AI & Machine Learning": [
        "ai", "ml", "machine learning", "llm", "deep learning", "nlp",
        "computer vision", "data scientist", "pytorch", "tensorflow", "genai",
    ],
    "Cloud & Infrastructure": [
        "devops", "cloud", "aws", "azure", "gcp", "kubernetes", "k8s",
        "docker", "terraform", "sre", "infrastructure", "platform engineer",
    ],
    "Frontend & Product": [
        "frontend", "react", "vue", "angular", "ui/ux", "product designer",
        "next.js", "nextjs", "web developer",
    ],
    "Backend & Core Systems": [
        "backend", "python", "golang", "java", "node", "rust", "c++",
        "distributed systems", "database", "api developer", "software engineer",
    ],
    "Sales & GTM Growth": [
        "sales", "bdr", "sdr", "account executive", "marketing", "growth",
        "business development", "customer success",
    ],
    "Security & Compliance": [
        "security", "infosec", "cyber", "compliance", "soc2", "penetration",
        "appsec",
    ],
}


def extract_domain(url: str) -> str:
    """Extract clean base domain from a URL (e.g. 'https://www.example.com/about' -> 'example.com')."""
    if not url or not isinstance(url, str):
        return ""

    raw = url.strip()
    if "://" not in raw:
        raw = f"https://{raw}"

    try:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        # Ensure it has at least one dot (domain.tld)
        if "." in host and not host.endswith("."):
            return host
        return ""
    except Exception:
        return ""


def clean_and_validate_email(email: str, company_domain: str = "") -> Optional[str]:
    """Validate RFC compliance, filter out noise, image extensions, and placeholder domains."""
    if not email or not isinstance(email, str):
        return None

    cleaned = email.strip().lower()
    if not EMAIL_REGEX.fullmatch(cleaned):
        return None

    # Check for invalid file extensions
    if any(cleaned.endswith(ext) for ext in INVALID_EMAIL_EXTENSIONS):
        return None

    user, _, domain = cleaned.partition("@")
    if not user or not domain:
        return None

    if any(domain == junk or domain.endswith(f".{junk}") for junk in JUNK_DOMAINS):
        return None

    if any(tracker in domain for tracker in ("sentry", "ingest", "bugsnag", "datadog", "newrelic", "rollbar")):
        return None

    if user in {"user", "test", "yourname", "name", "email"}:
        return None

    # If company_domain is provided, strictly enforce company domain match
    if company_domain:
        target_dom = company_domain.lower().strip()
        if not (domain == target_dom or domain.endswith(f".{target_dom}")):
            return None

    return cleaned



def check_domain_mx_doh(client: httpx.Client, domain: str) -> Tuple[bool, str, List[str]]:
    """Verify MX records over HTTPS using Cloudflare DoH (port 443, 100% GitHub Actions safe)."""
    if not domain:
        return False, "None", []

    doh_url = f"https://cloudflare-dns.com/dns-query?name={domain}&type=MX"
    headers = {"Accept": "application/dns-json"}

    try:
        resp = client.get(doh_url, headers=headers, timeout=6.0)
        if resp.status_code != 200:
            # Fallback to Google DoH
            google_url = f"https://dns.google/resolve?name={domain}&type=MX"
            resp = client.get(google_url, headers={"Accept": "application/json"}, timeout=6.0)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("Status") == 0 and "Answer" in data:
                answers = data["Answer"]
                mx_records = [
                    ans.get("data", "").strip().rstrip(".")
                    for ans in answers
                    if ans.get("type") == 15 or "data" in ans
                ]
                if mx_records:
                    rec_str = " ".join(mx_records).lower()
                    if "google" in rec_str or "aspmx" in rec_str:
                        provider = "Google Workspace"
                    elif "outlook" in rec_str or "mail.protection.outlook.com" in rec_str:
                        provider = "Microsoft 365"
                    elif "zoho" in rec_str:
                        provider = "Zoho Mail"
                    elif "proton" in rec_str:
                        provider = "ProtonMail"
                    elif "mimecast" in rec_str:
                        provider = "Mimecast"
                    elif "barracuda" in rec_str:
                        provider = "Barracuda"
                    else:
                        provider = "Custom / Enterprise MX"
                    return True, provider, mx_records

        return False, "None", []
    except Exception as e:
        logger.debug("DoH MX check error for %s: %s", domain, e)
        return False, "None", []


def crawl_contact_pages(client: httpx.Client, website_url: str) -> Tuple[List[str], str]:
    """Targeted crawl of 5 high-yield pages (/contact, /about, /privacy, security.txt)."""
    clean_base = website_url.strip()
    if not clean_base.startswith("http"):
        clean_base = f"https://{clean_base}"

    domain = extract_domain(clean_base)
    found_emails: Set[str] = set()
    first_contact_url = ""

    for path in TARGET_CRAWL_PATHS:
        target_url = urljoin(clean_base, path)
        try:
            resp = client.get(target_url, timeout=5.0, follow_redirects=True)
            if resp.status_code != 200:
                continue

            content_text = resp.text
            if not first_contact_url and path in {"/contact", "/contact-us", "/about"}:
                first_contact_url = target_url

            # 1. Parse mailto: links via BeautifulSoup
            try:
                soup = BeautifulSoup(content_text, "html.parser")
                for mailto in soup.select('a[href^="mailto:"]'):
                    href = mailto.get("href", "")
                    raw_email = href.replace("mailto:", "").split("?")[0].strip()
                    cleaned = clean_and_validate_email(raw_email, domain)
                    if cleaned:
                        found_emails.add(cleaned)
                        if not first_contact_url:
                            first_contact_url = target_url
            except Exception:
                pass

            # 2. Text regex scan
            matches = EMAIL_REGEX.findall(content_text)
            for m in matches:
                cleaned = clean_and_validate_email(m, domain)
                if cleaned:
                    found_emails.add(cleaned)
                    if not first_contact_url:
                        first_contact_url = target_url

            # If we found at least 2 distinct emails, stop early to optimize speed
            if len(found_emails) >= 4:
                break

        except Exception as e:
            logger.debug("Failed visiting %s: %s", target_url, e)
            continue

    return sorted(list(found_emails)), first_contact_url


def generate_email_permutations(founders_str: str, domain: str) -> List[str]:
    """Generate high-probability email permutations for founders/decision makers."""
    if not founders_str or not domain:
        return []

    # Clean domain
    domain = domain.lower().strip()
    # Handle list or comma/semicolon/and separated founders
    people = re.split(r"[,;&]|\band\b", founders_str, flags=re.IGNORECASE)
    permutations: List[str] = []

    for p in people:
        p_clean = re.sub(r"[^a-zA-Z\s]", "", p).strip().lower()
        parts = [part for part in p_clean.split() if len(part) > 1]
        if not parts:
            continue

        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""

        # Deliverable permutations
        candidates = [
            f"{first}@{domain}",
        ]
        if last:
            candidates.extend([
                f"{first}.{last}@{domain}",
                f"{first[0]}.{last}@{domain}",
                f"{first}{last}@{domain}",
            ])

        for cand in candidates:
            if cand not in permutations:
                permutations.append(cand)

    return permutations


def tag_hiring_intent(job_titles: Any) -> List[str]:
    """Classify hiring intent signals based on active job openings."""
    if not job_titles:
        return []

    if isinstance(job_titles, str):
        text_corpus = job_titles.lower()
    elif isinstance(job_titles, (list, set, tuple)):
        text_corpus = " ".join(str(t) for t in job_titles).lower()
    else:
        text_corpus = str(job_titles).lower()

    signals: List[str] = []
    for signal_name, keywords in HIRING_INTENT_MAP.items():
        if any(re.search(r"\b" + re.escape(kw) + r"\b", text_corpus) for kw in keywords):
            signals.append(signal_name)

    return signals


def resolve_company_domain(company_name: str, client: Optional[httpx.Client] = None) -> str:
    """Resolve base domain from company name using fast Clearbit autocomplete (zero API key)."""
    if not company_name or not isinstance(company_name, str):
        return ""

    clean_name = re.sub(
        r"\b(pvt|ltd|limited|llc|inc|corp|services|technologies|private)\b",
        "",
        company_name,
        flags=re.IGNORECASE,
    ).strip()
    if not clean_name:
        clean_name = company_name.strip()

    try:
        url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={clean_name}"
        c = client if client is not None else httpx
        resp = c.get(url, timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("domain"):
                return data[0]["domain"].lower().strip()
    except Exception:
        pass
    return ""


def enrich_single_company(company: Dict[str, Any], client: httpx.Client) -> Dict[str, Any]:
    """Enrich a single company profile with verified domain, MX status, emails, and hiring intent."""
    name = (company.get("company_name") or company.get("company") or "").strip()
    website = (company.get("company_website") or "").strip()
    domain = extract_domain(website)

    if not domain and name:
        domain = resolve_company_domain(name, client)
        if domain and not website:
            website = f"https://{domain}"

    mx_verified = False
    mx_provider = "None"
    records: List[str] = []

    if domain:
        mx_verified, mx_provider, records = check_domain_mx_doh(client, domain)

    emails_found: List[str] = []
    contact_url = ""
    if website:
        emails_found, contact_url = crawl_contact_pages(client, website)

    founders = str(company.get("founders") or "").strip()
    lead_candidates = generate_email_permutations(founders, domain)


    # Job titles analysis
    job_titles = company.get("job_titles") or []
    intent_signals = tag_hiring_intent(job_titles)

    # Open roles count
    total_jobs = company.get("total_jobs_posted") or (1 if company.get("title") else 0)

    # Format sample job titles
    if isinstance(job_titles, list):
        sample_titles = ", ".join(job_titles[:3])
    else:
        sample_titles = str(job_titles)[:100]

    return {
        "company_name": name,
        "company_website": website,
        "company_domain": domain,
        "mx_verified": mx_verified,
        "mx_provider": mx_provider,
        "emails_found": ", ".join(emails_found),
        "lead_email_candidates": ", ".join(lead_candidates),
        "contact_page_url": contact_url,
        "founders": founders,
        "headquarters": str(company.get("headquarters") or "").strip(),
        "company_stage": str(company.get("company_stage") or "").strip(),
        "total_funding": str(company.get("total_funding") or "").strip(),
        "hiring_intent_signals": ", ".join(intent_signals),
        "open_roles_count": total_jobs,
        "sample_job_titles": sample_titles,
    }


def enrich_companies_to_leads(
    companies: List[Dict[str, Any]],
    max_workers: int = 5,
) -> List[Dict[str, Any]]:
    """Enrich a collection of company dicts into verified B2B leads using concurrent workers."""
    if not companies:
        return []

    leads: List[Dict[str, Any]] = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    with httpx.Client(headers=headers, timeout=8.0, follow_redirects=True) as client:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_comp = {
                executor.submit(enrich_single_company, comp, client): comp
                for comp in companies
            }
            for future in as_completed(future_to_comp):
                try:
                    lead = future.result()
                    leads.append(lead)
                except Exception as e:
                    logger.warning("Error enriching company lead: %s", e)

    return leads


__all__ = [
    "LEAD_FIELDS",
    "extract_domain",
    "resolve_company_domain",
    "clean_and_validate_email",
    "check_domain_mx_doh",
    "crawl_contact_pages",
    "generate_email_permutations",
    "tag_hiring_intent",
    "enrich_single_company",
    "enrich_companies_to_leads",
    "save_leads_to_csv",
    "save_leads_to_json",
]


