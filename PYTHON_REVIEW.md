# Python Codebase Review & Actionable Roadmap (`/python-review`)

**Date**: September 6, 2026  
**Repository**: `Rohanpatel16/naukri-scraper`  
**Review Scope**: All 22 `.py` source files (Package modules, CLI runners, and Test suite)  
**Static Analysis**: `ruff 0.9.9` (0 errors, 0 warnings)  
**Test Suite**: `pytest 9.1.1` (31 / 31 tests passing in 3.60s)  
**Overall Verdict**: **PASS (Production-Ready)**

---

## 1. Executive Summary

This codebase is a high-performance, anti-bot resilient scraping platform built for **Naukri.com** and **Wellfound.com**, supplemented by multi-tiered corporate enrichment engines (**Inc42 Datalabs**, **AmbitionBox**, **Clearbit**, and **DuckDuckGo Search**).

### Key Strengths
- **Fast Execution Paths**: Sitemap streaming avoids browser overhead for keyword searches; Playwright route-blocking cuts out image/media downloads on heavy browser pages.
- **Resilient Reverse Engineering**: Wellfound scraper uses GraphQL network response sniffing before falling back to DOM parsing, extracting clean structured JSON directly from the platform.
- **Strong Test Foundation**: 31 unit and integration tests verify schema contracts, date parsing, URL decoding, company aggregation, and CLI dispatch.
- **Zero Critical Security Vulnerabilities**: No hardcoded secrets, no SQL/command injection vectors (`subprocess.run` uses safe list args), and safe data parsing.

---

## 2. File-by-File Technical Audit

### A. Core Package (`naukri_scraper/`)

#### 1. [`naukri_scraper/config.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/config.py) (137 lines)
- **Role**: Centralized configuration, base URLs, HTTP headers, city mappings, and canonical field schemas.
- **Quality**: Clean, focused, and immutable. Defines canonical `JOB_FIELDS` (26 fields) and `COMPANY_FIELDS` (20 fields).
- **Opportunity**: Convert schemas to `TypedDict` or `dataclass` definitions for static type checking across the entire pipeline.

#### 2. [`naukri_scraper/parser.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/parser.py) (164 lines)
- **Role**: Parses and cleans individual job URLs from Naukri sitemaps. Extracts job IDs, posting dates (DDMMYY), experience ranges, locations, and company names from URL slugs without network requests.
- **Quality**: Pure functions with zero side-effects. Safe regex parsing with fallbacks.
- **Opportunity**: Add regex pre-compilation (`re.compile`) at module level for high-throughput loops when scanning 50,000+ sitemap URLs.

#### 3. [`naukri_scraper/scraper.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/scraper.py) (171 lines)
- **Role**: High-speed XML sitemap stream scraper for Naukri. Automatically discovers city-specific sitemaps and decompresses gzip streams on the fly.
- **Quality**: Simple, robust session management with exponential backoff retries.
- **Opportunity**:
  - Convert from synchronous `requests.Session` to `httpx.AsyncClient` or add `ThreadPoolExecutor` to stream multiple sitemaps in parallel.
  - Stream XML using `xml.etree.ElementTree.iterparse` rather than regex findall over large in-memory decompressed strings for lower memory footprint.

#### 4. [`naukri_scraper/browser_scraper.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/browser_scraper.py) (847 lines)
- **Role**: Playwright async multi-tab browser scraper for custom Naukri search URLs with live AmbitionBox and Clearbit company resolution.
- **Quality**: Anti-bot evasion features (stealth flags, custom navigator overrides), aggressive route blocking (aborts stylesheets, images, fonts, analytics).
- **Opportunity**:
  - **High Complexity / Large File**: At 847 lines, this file contains browser automation, AmbitionBox parsing, Clearbit lookup, and DDGS searches.
  - **Action**: Extract company resolution logic (AmbitionBox, Clearbit, DDGS) into a dedicated `naukri_scraper/company_resolver.py` module.

#### 5. [`naukri_scraper/inc42_scraper.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/inc42_scraper.py) (335 lines)
- **Role**: Asynchronous scraper for Inc42 Datalabs startup profiles (headquarters, founders, founding year, funding stage, total funding, revenue).
- **Quality**: Excellent slug generation heuristics (`clean_company_slugs`), robust JSON-LD schema parsing, and clean async batching (`asyncio.gather` with semaphores).
- **Opportunity**: Cache 404 responses for companies not indexed in Inc42 to prevent repeat lookups.

#### 6. [`naukri_scraper/wellfound_scraper.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/wellfound_scraper.py) (596 lines)
- **Role**: Dump & Filter scraper for Wellfound. Employs GraphQL network response sniffing to capture structured data before falling back to DOM cards.
- **Quality**: High efficiency due to response interception. Accurate relative date calculation (`parse_posted_age_days`).
- **Opportunity**:
  - Duplicate `EXCLUDE_DDGS_DOMAINS` and company query cleaners shared with `browser_scraper.py`.
  - Action: Centralize company domain search in a shared resolver.

#### 7. [`naukri_scraper/exporter.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/exporter.py) (189 lines)
- **Role**: Aggregates raw job postings into unique company profile summaries and handles CSV/JSON export.
- **Quality**: Well-structured defaultdict aggregation; ensures directories exist before writing.
- **Opportunity**: Add Excel (`.xlsx`) export option via `openpyxl` or `pandas` for recruiters and non-technical business users.

#### 8. [`naukri_scraper/cli.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/cli.py) & [`wellfound_cli.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/wellfound_cli.py) (223 & 191 lines)
- **Role**: CLI parsing and progress reporting for Naukri and Wellfound respectively.
- **Quality**: Comprehensive arguments, clear CLI banner, execution timing metrics, and summary tables.
- **Opportunity**: Add a `--quiet` flag to suppress output for headless cron / CI environments.

#### 9. [`scraper.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/scraper.py) (95 lines)
- **Role**: Unified top-level router dispatching commands to `naukri`, `wellfound`, or diagnostic runners.
- **Quality**: Clean, zero lint errors, Windows UTF-8 console support.

---

### B. Test Suite (`tests/`)

| Test File | Lines | Tests | Description |
|---|---|---|---|
| [`tests/test_ambitionbox.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_ambitionbox.py) | 140 | 1 | Tests `__NEXT_DATA__` JSON extraction from AmbitionBox mock HTML. |
| [`tests/test_cli.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_cli.py) | 38 | 3 | Validates default and custom argument parsing for both CLIs. |
| [`tests/test_config.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_config.py) | 57 | 4 | Verifies headers, URLs, and field schema definitions. |
| [`tests/test_data_pipeline_dump.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_data_pipeline_dump.py) | 345 | 3 | Verifies 100% field population and dump file writing integrity. |
| [`tests/test_exporter.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_exporter.py) | 107 | 2 | Tests company aggregation and CSV/JSON output generation. |
| [`tests/test_inc42.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_inc42.py) | 107 | 2 | Verifies company slug generator and HTML metadata extraction. |
| [`tests/test_naukri_scraper.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_naukri_scraper.py) | 50 | 5 | Tests sitemap index fetching, gzip decompression, and stream parsing. |
| [`tests/test_parser.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_parser.py) | 86 | 6 | Tests slug decoding, experience extraction, and filtering. |
| [`tests/test_scraper_cli.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_scraper_cli.py) | 26 | 2 | Tests CLI sub-command execution via `subprocess.run`. |
| [`tests/test_wellfound.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/tests/test_wellfound.py) | 86 | 3 | Tests relative age parsing, company cleaning, and Wellfound aggregation. |
| **Total** | **1,042** | **31** | **All 31 tests passing in ~3.6s** |

---

## 3. High-Leverage Improvements: What We Can Do Next

### Priority 1: Architectural Modularization (DRY Enrichment)
- **Problem**: `browser_scraper.py` and `wellfound_scraper.py` duplicate:
  - `EXCLUDE_DDGS_DOMAINS` list (~25 domains repeated).
  - Corporate suffix cleaner regex (`pvt`, `ltd`, `technologies`, `solutions`).
  - DuckDuckGo search fallback logic.
  - Clearbit Autocomplete domain resolution.
- **Solution**: Create [`naukri_scraper/company_resolver.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/naukri_scraper/company_resolver.py):
  - Consolidates Tier 0 (Inc42), Tier 1 (AmbitionBox), Tier 2 (DDGS), and Tier 3 (Clearbit) into a unified async resolver.
  - Both Naukri and Wellfound scrapers import from this single module, reducing ~250 lines of duplicate code.

### Priority 2: Persistent Disk Caching for Company Domains
- **Problem**: Company domain lookups currently rely on an in-memory dictionary (`_COMPANY_WEBSITE_CACHE`) that resets after every script execution. If you run the scraper daily, you repeat lookups for companies like TCS, Infosys, Swiggy, and Zepto every single run.
- **Solution**: Implement lightweight local disk caching using SQLite or JSON (`data/.company_cache.sqlite` or `data/.cache.json`):
  - Checks local database first (< 1ms).
  - Skips network requests for previously resolved companies.
  - Eliminates DuckDuckGo rate limiting and dramatically accelerates scraping speed.

### Priority 3: Type Safety with `TypedDict` / Pydantic
- **Problem**: Records are passed as raw `Dict[str, Any]`. A typo like `job["cmpany"]` fails at runtime rather than compile-time.
- **Solution**:
  ```python
  from typing import TypedDict, Optional, List

  class JobRecord(TypedDict):
      job_id: str
      title: str
      company: str
      company_website: str
      location: str
      experience_text: str
      salary: str
      skills: str
      posted_date: str
      url: str

  class CompanyRecord(TypedDict):
      company_name: str
      company_website: str
      company_linkedin: str
      total_jobs_posted: int
      job_titles: List[str]
  ```

### Priority 4: Modern Packaging & Developer Experience (`pyproject.toml`)
- **Problem**: Currently relies solely on `requirements.txt`. There is no formal package installer.
- **Solution**: Add [`pyproject.toml`](file:///d:/Codinf%20projets/Naukri.com%20scraper/pyproject.toml):
  - Declares console entrypoints: `pip install -e .` enables `naukri-scraper` and `wellfound-scraper` directly in terminal.
  - Configures `ruff`, `pytest`, and `coverage` settings centrally.

### Priority 5: Async Parallelization for Sitemap Scraper
- **Problem**: `NaukriScraper` streams sitemaps sequentially.
- **Solution**: When multiple sitemaps match (e.g. 5 sitemaps for general tech), fetch and decompress sitemaps concurrently using `asyncio` or `concurrent.futures.ThreadPoolExecutor(max_workers=5)`, speeding up sitemap scraping by 3-4x.

---

## 4. Implementation Action Plan

| Phase | Action Item | Target File(s) | Benefit |
|:---:|---|---|---|
| **Phase 1** | Extract shared company resolution engine | `naukri_scraper/company_resolver.py` | Eliminates ~250 lines of duplicate code across scrapers. |
| **Phase 2** | Add persistent SQLite domain cache | `naukri_scraper/company_resolver.py` | 10x faster enrichment on repeat runs; avoids rate limits. |
| **Phase 3** | Define `TypedDict` schemas | `naukri_scraper/config.py` | Static typing, autocompletion, IDE error prevention. |
| **Phase 4** | Add `pyproject.toml` | `pyproject.toml` | Enables `pip install -e .` and CLI binary commands. |
| **Phase 5** | Parallelize sitemap fetching | `naukri_scraper/scraper.py` | 3-4x speedup on multi-sitemap queries. |

---

## 5. Security & Compliance Checklist

- [x] **No hardcoded secrets**: All API endpoints and lookups are public or configurable via environment variables.
- [x] **Safe process execution**: `subprocess.run` calls in test runners use explicit argument lists without `shell=True`.
- [x] **Anti-hang timeouts**: Hard bounded timeouts (10s to 30s) on all HTTP requests and Playwright navigations.
- [x] **Safe file paths**: Exporters use `pathlib.Path.mkdir(parents=True, exist_ok=True)` ensuring safe directory creation.
- [x] **Automated CI/CD validation**: 4 GitHub Actions workflows run the TDD test gate on every push and dispatch.
