"""Command-Line Interface for the B2B Lead Generation & Verification Engine."""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .lead_enricher import (
    enrich_companies_to_leads,
    save_leads_to_csv,
    save_leads_to_json,
)

# UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(asctime)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def print_banner() -> None:
    banner = """
============================================================
       B2B LEAD GENERATION & VERIFICATION ENGINE
============================================================
"""
    print(banner)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert hiring company records into verified B2B leads with deliverable emails and hiring intent."
    )
    parser.add_argument(
        "-i", "--input",
        default=None,
        help="Input CSV or JSON containing scraped companies (e.g. data/naukri_companies.csv)",
    )
    parser.add_argument(
        "-o", "--output",
        default="data/leads.csv",
        help="Output filepath for verified leads (default: data/leads.csv)",
    )
    parser.add_argument(
        "-d", "--domain",
        default=None,
        help="Directly inspect and extract leads for a specific domain/website (e.g. -d razorpay.com)",
    )
    parser.add_argument(
        "--founders",
        default="",
        help="Optional founder/decision maker names when using --domain (e.g. --founders 'Harshil Mathur, Shashank Kumar')",
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=5,
        help="Concurrent HTTP workers for verification and crawling (default: 5)",
    )
    parser.add_argument(
        "-n", "--max-leads",
        type=int,
        default=None,
        help="Limit number of companies to enrich",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable detailed debug logs",
    )
    return parser.parse_args(argv)


def load_companies_from_file(filepath: str) -> List[Dict[str, Any]]:
    path = Path(filepath)
    if not path.exists():
        print(f"[!] Error: File not found: {path.resolve()}")
        return []

    companies: List[Dict[str, Any]] = []
    if path.suffix.lower() == ".json":
        import json
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                companies = data
    else:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            companies = list(reader)

    return companies


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)
    print_banner()

    start_time = time.time()

    # 1. Single-domain mode
    if args.domain:
        print(f"[*] Target Domain : {args.domain}")
        if args.founders:
            print(f"[*] Founders      : {args.founders}")
        print("-" * 60)

        mock_company = {
            "company_name": args.domain.split(".")[0].title(),
            "company_website": f"https://{args.domain}",
            "founders": args.founders,
            "job_titles": ["Engineering", "Leadership"],
            "total_jobs_posted": 1,
        }
        leads = enrich_companies_to_leads([mock_company], max_workers=1)

    # 2. Bulk file enrichment mode
    elif args.input:
        print(f"[*] Input File    : {args.input}")
        print(f"[*] Output File   : {args.output}")
        print(f"[*] Concurrency   : {args.workers} workers")
        print("-" * 60)

        companies = load_companies_from_file(args.input)
        if not companies:
            print("[!] No companies found to enrich.")
            return 1

        if args.max_leads:
            companies = companies[:args.max_leads]

        print(f"[+] Loaded {len(companies)} companies. Starting verification and enrichment...")
        leads = enrich_companies_to_leads(companies, max_workers=args.workers)

    else:
        # Check default paths if neither is supplied
        default_candidates = [
            "data/naukri_companies.csv",
            "naukri_companies.csv",
            "data/linkedin_companies.csv",
            "data/wellfound_companies.csv",
        ]
        found_input = None
        for cand in default_candidates:
            if Path(cand).exists():
                found_input = cand
                break

        if not found_input:
            print("Usage: python scraper.py leads -i <companies.csv> -o <leads.csv>")
            print("   or: python scraper.py leads -d <domain.com> [--founders 'Name']")
            return 1

        print(f"[*] Auto-detected Input File: {found_input}")
        companies = load_companies_from_file(found_input)
        if args.max_leads:
            companies = companies[:args.max_leads]
        print(f"[+] Loaded {len(companies)} companies. Starting verification and enrichment...")
        leads = enrich_companies_to_leads(companies, max_workers=args.workers)

    elapsed = time.time() - start_time

    # Output stats
    mx_verified = sum(1 for lead in leads if lead.get("mx_verified"))
    emails_found_count = sum(1 for lead in leads if lead.get("emails_found"))
    candidates_count = sum(1 for lead in leads if lead.get("lead_email_candidates"))

    print("-" * 60)
    print(f"[+] Lead Generation completed in {elapsed:.2f} seconds.")
    print(f"[+] Total Leads Processed      : {len(leads):,}")
    print(f"[+] MX Verified Inboxes        : {mx_verified:,}/{len(leads):,} ({(mx_verified / len(leads) * 100 if leads else 0):.1f}%)")
    print(f"[+] Direct Found Public Emails : {emails_found_count:,}/{len(leads):,} companies")
    print(f"[+] Decision-Maker Permutations: {candidates_count:,}/{len(leads):,} companies")

    # Save output
    if args.output.endswith(".json"):
        out_path = save_leads_to_json(leads, args.output)
    else:
        out_path = save_leads_to_csv(leads, args.output)

    print(f"\n[+] Verified B2B Leads saved to: {out_path.resolve()}\n")

    # Preview top 3 leads
    print("Verified Leads Preview:")
    print("=" * 60)
    for i, lead in enumerate(leads[:3], 1):
        print(f"#{i} {lead['company_name']} ({lead['company_domain'] or 'No domain'})")
        print(f"   MX Verified   : {lead['mx_verified']} [{lead['mx_provider']}]")
        if lead['emails_found']:
            print(f"   Direct Emails : {lead['emails_found']}")
        if lead['lead_email_candidates']:
            print(f"   Candidates    : {lead['lead_email_candidates']}")
        if lead['hiring_intent_signals']:
            print(f"   Hiring Intent : {lead['hiring_intent_signals']}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
