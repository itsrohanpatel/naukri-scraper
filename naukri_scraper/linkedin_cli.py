"""Command-Line Interface for the LinkedIn Job Scraper."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

from .exporter import aggregate_companies, save_companies_to_csv, save_to_csv
from .linkedin_scraper import LinkedInScraper

# Windows UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def setup_logging(verbose: bool = False) -> None:
    """Configure console logging level and format."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(asctime)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def print_banner() -> None:
    banner = """
============================================================
              LINKEDIN JOB & COMPANY SCRAPER
============================================================
"""
    print(banner)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fast, anti-bot resilient scraper for LinkedIn jobs with date limits and company enrichment."
    )
    parser.add_argument(
        "-k", "--keywords",
        nargs="+",
        default=None,
        help="Job title or technology keywords to search (e.g. -k python devops aws)",
    )
    parser.add_argument(
        "-l", "--location",
        default=None,
        help="City, country, or location filter (e.g. -l Bangalore, -l India, -l Remote)",
    )
    parser.add_argument(
        "-u", "--url",
        default=None,
        help="Direct custom LinkedIn search URL",
    )
    parser.add_argument(
        "-D", "--days",
        type=int,
        default=None,
        help="Only include jobs posted within the last N days (e.g. -D 1, -D 7, -D 14)",
    )
    parser.add_argument(
        "-H", "--hours",
        type=int,
        default=None,
        help="Only include jobs posted within the last N hours (e.g. -H 12, -H 24, -H 48)",
    )
    parser.add_argument(
        "-n", "--max-jobs",
        type=int,
        default=50,
        help="Maximum jobs to collect (default: 50)",
    )
    parser.add_argument(
        "-o", "--output",
        default="data/linkedin_companies.csv",
        help="Output CSV filepath for aggregated companies (default: data/linkedin_companies.csv)",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Force Playwright browser automation with infinite scroll instead of fast HTTP Guest API",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable detailed debug logs",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)
    print_banner()

    start_time = time.time()

    time_filter_str = "All Time"
    if args.hours:
        time_filter_str = f"Last {args.hours} Hours"
    elif args.days:
        time_filter_str = f"Last {args.days} Days"

    kw_display = " ".join(args.keywords) if args.keywords else "Software Engineer"
    print(f"[*] Target Keywords : {kw_display}")
    print(f"[*] Location Filter : {args.location or 'India'}")
    print(f"[*] Time Limit      : {time_filter_str}")
    print(f"[*] Max Jobs Target : {args.max_jobs}")
    print(f"[*] Engine          : {'Playwright Browser' if args.browser or args.url else 'Fast HTTP Guest API'}")
    print(f"[*] Output CSV      : {args.output}\n" + "-" * 60)

    scraper = LinkedInScraper()
    jobs = scraper.scrape(
        keywords=args.keywords,
        location=args.location,
        url=args.url,
        max_jobs=args.max_jobs,
        days=args.days,
        hours=args.hours,
        use_browser=args.browser,
    )

    elapsed = time.time() - start_time

    if not jobs:
        print("[!] No jobs found matching the current filters.")
        return 0

    # Aggregate companies
    companies = aggregate_companies(jobs)
    resolved_web = sum(1 for c in companies if c.get("company_website"))
    pct_web = (resolved_web / len(companies) * 100.0) if companies else 0.0

    print("-" * 60)
    print(f"[+] Scraping finished in {elapsed:.2f} seconds.")
    print(f"[+] Total Jobs Scraped     : {len(jobs):,}")
    print(f"[+] Unique Companies       : {len(companies):,}")
    print(f"[+] Website Resolution Rate: {resolved_web:,}/{len(companies):,} ({pct_web:.1f}%)")

    # Save outputs
    out_dir = Path(args.output).parent
    jobs_out_path = out_dir / "linkedin_jobs.csv" if out_dir != Path(".") else Path("linkedin_jobs.csv")

    save_to_csv(jobs, str(jobs_out_path))
    save_companies_to_csv(companies, args.output)

    print(f"\n[+] Jobs saved to               : {jobs_out_path.resolve()}")
    print(f"[+] Company Profiles saved to   : {Path(args.output).resolve()}\n")

    # Display preview
    print("Top Hiring Companies Preview:")
    print("=" * 60)
    for i, c in enumerate(companies[:5], 1):
        print(f"#{i} {c['company_name']} ({c['total_jobs_posted']} job postings)")
        if c.get("company_website"):
            print(f"   Website   : {c['company_website']}")
        if c.get("company_linkedin"):
            print(f"   LinkedIn  : {c['company_linkedin']}")
        print(f"   Job Titles: {c['job_titles'][:100]}...")
        print(f"   Locations : {c['locations']}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
