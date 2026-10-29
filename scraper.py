"""Unified Entry Point for Naukri & Wellfound Job Scrapers.

Usage:
    # 1. Naukri Scraper (Default)
    python scraper.py --url "<naukri_search_url>"
    python scraper.py --keywords python devops --location Bangalore
    python scraper.py naukri --url "<naukri_search_url>"

    # 2. Wellfound Scraper
    python scraper.py wellfound --url "https://wellfound.com/role/l/software-engineer/india" --days 7

    # 3. LinkedIn Scraper
    python scraper.py linkedin --keywords python devops --location India --days 3
    python scraper.py linkedin --url "<linkedin_search_url>"

    # 4. Diagnostic & Verification Tools
    python scraper.py test inc42 --company "Zepto"
    python scraper.py test ambitionbox --url "<ambitionbox_url>"
"""

from __future__ import annotations

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
        from naukri_scraper.wellfound_cli import main as wellfound_main
        return wellfound_main(argv[1:])

    elif argv and argv[0].lower() == "linkedin":
        from naukri_scraper.linkedin_cli import main as linkedin_main
        return linkedin_main(argv[1:])

    elif argv and argv[0].lower() == "naukri":
        from naukri_scraper.cli import main as naukri_main
        return naukri_main(argv[1:])

    elif argv and argv[0].lower() == "leads":
        from naukri_scraper.lead_cli import main as lead_main
        return lead_main(argv[1:])

    elif argv and argv[0].lower() == "test":
        sub = argv[1].lower() if len(argv) > 1 else ""
        rest = argv[2:]
        if sub == "inc42":
            from tests.test_inc42 import main as inc42_test_main
            return inc42_test_main(rest) or 0
        elif sub == "ambitionbox":
            from tests.test_ambitionbox import main as ab_test_main
            return ab_test_main(rest) or 0
        else:
            print("Usage: python scraper.py test [inc42|ambitionbox] [options]")
            return 1

    # Default fallback to Naukri CLI (maintains 100% backward compatibility)
    from naukri_scraper.cli import main as naukri_main
    return naukri_main(argv)


if __name__ == "__main__":
    sys.exit(main())
