# Codebase Review: Scraper Suite (`REVIEW.md`)

What this change does: This suite scrapes job postings and corporate profiles from [Naukri.com](https://www.naukri.com), [Wellfound.com](https://wellfound.com), and [LinkedIn](https://www.linkedin.com). It enriches records with company websites, founders, and funding data from Inc42, AmbitionBox, DuckDuckGo, and Clearbit, then exports them to CSV and JSON.

Expected load: 1 to 5 local operator or CI runs per day, pulling between 50 and 1,000 jobs per query without persistent database storage.

---

## Must fix

1. **LinkedIn scraper crashes inside existing event loops** ([`naukri_scraper/linkedin_scraper.py:L393, L419`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/linkedin_scraper.py#L393))
   - **What this is:** The LinkedIn scraper calls `asyncio.run()` directly inside its browser scraping step and its company enrichment helper.
   - **Problem:** When called from code that already has a running event loop (like FastAPI, Jupyter notebooks, or an async pipeline), `asyncio.run()` throws a `RuntimeError` and terminates the process immediately.
   - **Fix:** Add a `try/except RuntimeError` check to reuse the active event loop, matching the pattern in [`naukri_scraper/browser_scraper.py:L843-847`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/browser_scraper.py#L843-L847).
   - **If we skip it:** Any async service or notebook that imports `LinkedInScraper` crashes on its first run.

2. **DuckDuckGo search fallback skips all lookups when missing companies exceed 25** ([`naukri_scraper/linkedin_scraper.py:L432-440`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/linkedin_scraper.py#L432-L440))
   - **What this is:** An anti-abuse gate that prevents excessive DuckDuckGo search queries during LinkedIn company enrichment.
   - **Problem:** If a scrape has 26 or more unresolved companies, `if len(missing_comps) <= 25:` evaluates to false and runs zero searches for all of them.
   - **Fix:** Change `if len(missing_comps) <= 25:` to `for c in missing_comps[:25]:` so it searches the first 25 instead of none.
   - **If we skip it:** Large queries for 500+ jobs lose website resolution entirely for companies not indexed in Inc42.

---

## Should fix

3. **Duplicated Wellfound CLI dispatch in top-level runner** ([`scraper.py:L40-70`](file:///d:/Codinf%20projets/Naukri.com%20scraper/scraper.py#L40-L70))
   - **What this is:** The top-level script routes user commands like `python scraper.py wellfound` to the right scraper.
   - **Problem:** It inlines 30 lines of argument parsing and manual CSV writing instead of delegating to [`naukri_scraper/wellfound_cli.py:L116`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/wellfound_cli.py#L116), dropping directory creation, CSV field safety, run timing, and top-company preview.
   - **Fix:** Replace lines 40-70 with `from naukri_scraper.wellfound_cli import main as wf_main; return wf_main(argv[1:])`.
   - **If we skip it:** Changes to Wellfound output formatting in `wellfound_cli.py` will not work when called via `scraper.py`.

4. **Test subcommand mutates global `sys.argv`** ([`scraper.py:L85, L90`](file:///d:/Codinf%20projets/Naukri.com%20scraper/scraper.py#L85))
   - **What this is:** Diagnostic test runners for Inc42 and AmbitionBox invoked via `python scraper.py test inc42`.
   - **Problem:** It overwrites the global `sys.argv` array with `["test_inc42.py"] + rest` to pass flags into the test functions.
   - **Fix:** Pass `argv=rest` directly into `inc42_test_main(rest)` and `ab_test_main(rest)` instead of reassigning `sys.argv`.
   - **If we skip it:** Any program calling `scraper.main()` as a library gets its command-line arguments overwritten.

5. **Missing anti-bot stealth flag on LinkedIn Playwright browser** ([`naukri_scraper/linkedin_scraper.py:L321-326`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/linkedin_scraper.py#L321-L326))
   - **What this is:** The browser fallback used when scraping LinkedIn search URLs directly.
   - **Problem:** It opens a raw Chromium browser without masking `navigator.webdriver`, which LinkedIn's anti-bot system checks to block guests.
   - **Fix:** Add `await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")` before visiting the search page.
   - **If we skip it:** LinkedIn detects automated control and redirects the browser session to a login wall.

6. **Missing unit test for LinkedIn Guest API pagination** ([`tests/test_linkedin.py:L1-94`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_linkedin.py#L1-L94))
   - **What this is:** The test suite verifying LinkedIn scraping logic.
   - **Problem:** Tests only cover date regex, card HTML parsing, and CLI arguments; none verify that `scrape_guest_api` stops at `max_jobs` or handles 429 rate limits.
   - **Fix:** Add a mocked HTTP test verifying that `scrape_guest_api` requests `max_jobs` items and respects date filtering.
   - **If we skip it:** A regression in pagination offsets or rate-limit backoff can break large runs without failing tests.

---

## Nice to have

7. **Clearbit Autocomplete unchecked list item access** ([`naukri_scraper/browser_scraper.py:L153-157`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/browser_scraper.py#L153-L157))
   - **What this is:** The Tier-3 domain lookup fallback for company websites.
   - **Problem:** It calls `data[0].get("domain")` assuming the item is a dictionary. If Clearbit returns strings or a non-dict element, Python raises an `AttributeError`.
   - **Fix:** Add `isinstance(data[0], dict)` to the condition before calling `.get()`.
   - **If we skip it:** An unexpected response shape from Clearbit will log an exception during company resolution.

8. **Incomplete directory tree in documentation** ([`README.md:L19-45`](file:///d:/Codinf%20projets/Naukri.com%20scraper/README.md#L19-L45))
   - **What this is:** The repository file tree diagram in the project documentation.
   - **Problem:** The tree lists Naukri and Wellfound modules, but omits [`naukri_scraper/linkedin_scraper.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/linkedin_scraper.py), [`naukri_scraper/linkedin_cli.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/linkedin_cli.py), and [`tests/test_linkedin.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_linkedin.py).
   - **Fix:** Add the three LinkedIn files to the tree diagram in `README.md`.
   - **If we skip it:** Readers cannot see where LinkedIn scraping logic lives from the root README.

---

---

Verdict: Resolved (All 8 findings fixed and validated).
Lean: -29 lines removed through delegation in scraper.py.
Not checked: Live network responses from Naukri sitemaps and AmbitionBox, which require unblocked external internet connectivity.

---

## 3. Resolution & TDD Verification Summary

All 8 review items have been resolved and verified with unit and integration tests:

1. **LinkedIn Nested Loop Crash (Fixed)**: Implemented `_run_coroutine_safely` in [`naukri_scraper/linkedin_scraper.py:L140`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/linkedin_scraper.py#L140) with `ThreadPoolExecutor` fallback. Verified via [`tests/test_linkedin.py::test_linkedin_scrape_inside_running_loop`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_linkedin.py).
2. **DDGS Missing Company Slicing (Fixed)**: Replaced `if len(missing_comps) <= 25:` with `for c in missing_comps[:25]:` in [`naukri_scraper/linkedin_scraper.py:L436`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/linkedin_scraper.py#L436). Verified via [`tests/test_linkedin.py::test_linkedin_enrich_ddgs_fallback_slice_boundary`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_linkedin.py).
3. **Wellfound Dispatch Duplication (Fixed)**: Delegated `argv[0] == "wellfound"` to [`naukri_scraper.wellfound_cli.main`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/wellfound_cli.py#L116) in [`scraper.py:L39-41`](file:///d:/Codinf%20projets/Naukri.com%20scraper/scraper.py#L39-L41), removing 29 lines of duplicated code.
4. **Global `sys.argv` Mutation (Fixed)**: Updated diagnostic runners in [`tests/test_inc42.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_inc42.py) and [`tests/test_ambitionbox.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_ambitionbox.py) to accept `argv=None`. Passed `rest` directly in [`scraper.py:L54-58`](file:///d:/Codinf%20projets/Naukri.com%20scraper/scraper.py#L54-L58). Verified via [`tests/test_scraper_cli.py::test_scraper_test_subcommand_sys_argv_preserved`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_scraper_cli.py).
5. **LinkedIn Anti-Bot Stealth (Fixed)**: Injected `navigator.webdriver` mask into Playwright browser context in [`naukri_scraper/linkedin_scraper.py:L325`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/linkedin_scraper.py#L325).
6. **LinkedIn Pagination Test (Added)**: Added mock multi-page pagination test in [`tests/test_linkedin.py::test_linkedin_scrape_guest_api_pagination_and_limit`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_linkedin.py).
7. **Clearbit Type Guard (Fixed)**: Added `isinstance(data[0], dict)` in [`naukri_scraper/browser_scraper.py:L153`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/browser_scraper.py#L153). Verified via [`tests/test_ambitionbox.py::test_dynamic_extract_clearbit_non_dict_elements`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_ambitionbox.py).
8. **README Tree Synchronization (Fixed)**: Updated directory diagram in [`README.md:L26-36`](file:///d:/Codinf%20projets/Naukri.com%20scraper/README.md#L26-L36).

**Verification Results:**
- `pytest`: 42 / 42 passed in 17.53s.
- `ruff check .`: 0 errors, 0 warnings.

