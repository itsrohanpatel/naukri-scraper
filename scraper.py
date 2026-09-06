"""Unified Entry Point for Naukri & Wellfound Job Scrapers.

Usage:
    # 1. Naukri Scraper (Default)
    python scraper.py --url "<naukri_search_url>"
    python scraper.py --keywords python devops --location Bangalore
    python scraper.py naukri --url "<naukri_search_url>"

    # 2. Wellfound Scraper
    python scraper.py wellfound --url "https://wellfound.com/role/l/software-engineer/india" --days 7

    # 3. Diagnostic & Verification Tools
    python scraper.py test inc42 --company "Zepto"
    python scraper.py test ambitionbox --url "<ambitionbox_url>"
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # UTF-8 output on Windows consoles
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if argv and argv[0].lower() == "wellfound":
        from naukri_scraper.wellfound_cli import (
            parse_args as parse_wf_args,
            print_banner as print_wf_banner,
            setup_logging as setup_wf_logging,
            FIELDS as WF_FIELDS,
        )
        from naukri_scraper.wellfound_scraper import WellfoundScraper
        import csv
        from pathlib import Path

        args = parse_wf_args(argv[1:])
        setup_wf_logging(args.verbose)
        print_wf_banner()

        scraper = WellfoundScraper(headless=True, num_workers=args.workers)
        companies = scraper.scrape(
            search_url=args.url,
            max_pages=args.pages,
            days=args.days,
            hours=args.hours,
            raw_dump_path=args.raw_dump,
        )

        out_path = Path(args.output)
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=WF_FIELDS)
            writer.writeheader()
            writer.writerows(companies)

        print(f"\n[+] Saved {len(companies)} companies to: {out_path.resolve()}\n")
        return 0

    elif argv and argv[0].lower() == "naukri":
        from naukri_scraper.cli import main as naukri_main
        return naukri_main(argv[1:])

    elif argv and argv[0].lower() == "test":
        sub = argv[1].lower() if len(argv) > 1 else ""
        rest = argv[2:]
        if sub == "inc42":
            from tests.test_inc42 import main as inc42_test_main
            sys.argv = ["test_inc42.py"] + rest
            inc42_test_main()
            return 0
        elif sub == "ambitionbox":
            from tests.test_ambitionbox import main as ab_test_main
            sys.argv = ["test_ambitionbox.py"] + rest
            ab_test_main()
            return 0
        else:
            print("Usage: python scraper.py test [inc42|ambitionbox] [options]")
            return 1

    # Default fallback to Naukri CLI (maintains 100% backward compatibility)
    from naukri_scraper.cli import main as naukri_main
    return naukri_main(argv)


if __name__ == "__main__":
    sys.exit(main())
