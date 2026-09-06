# System Architecture & Technical Review (`/python-review`)

This document provides a comprehensive technical overview of the **Naukri & Wellfound Scraping Platform**, its multi-tiered company verification engine, and the automated TDD test infrastructure.

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Subsystem Deep Dives](#2-subsystem-deep-dives)
   - [Unified CLI Runner (`scraper.py`)](#subsystem-1-unified-cli-runner)
   - [Naukri Scraping Engine](#subsystem-2-naukri-scraping-engine)
   - [Wellfound Scraping Engine](#subsystem-3-wellfound-scraping-engine)
   - [4-Tier Company Verification & Enrichment](#subsystem-4-4-tier-company-verification--enrichment)
   - [Data Normalization & Export Pipelines](#subsystem-5-data-normalization--export-pipelines)
   - [Test Infrastructure & CI/CD](#subsystem-6-test-infrastructure--cicd)
3. [Data Contracts & Schemas](#3-data-contracts--schemas)
4. [Python Review Report (`/python-review`)](#4-python-review-report-python-review)
5. [CLI Commands Quick Reference](#5-cli-commands-quick-reference)

---

## 1. High-Level Architecture

```text
                               ┌────────────────────────────────┐
                               │  scraper.py (Unified Runner)   │
                               └───────────────┬────────────────┘
                                               │
                             ┌─────────────────┴─────────────────┐
                             │                                   │
                             ▼                                   ▼
                   ┌────────────────────┐              ┌────────────────────┐
                   │ 1. Naukri Scraper  │              │ 2.Wellfound Scraper│
                   │ - Sitemap Streamer │              │ - Dump & Filter    │
                   │ - Playwright Multi-│              │ - GraphQL Sniffing │
                   │   Tab Search URL   │              │ - Age Filtering    │
                   └─────────┬──────────┘              └─────────┬──────────┘
                             │                                   │
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                   ┌──────────────────────────────────────────────────────┐
                   │ 3. Tiered Company Enrichment Engine                  │
                   │ • Tier 0: Inc42 HTTP (Indian Startups & Funding)     │
                   │ • Tier 1: AmbitionBox (Ratings, Reviews, Headcount)  │
                   │ • Tier 2: DuckDuckGo Search (DDGS official websites) │
                   │ • Tier 3: Clearbit Autocomplete (Domain resolution)  │
                   └───────────────────────────┬──────────────────────────┘
                                               │
                                               ▼
                   ┌──────────────────────────────────────────────────────┐
                   │ 4. Exporters & Data Pipelines                        │
                   │ • data/naukri_companies.csv / naukri_jobs.csv        │
                   │ • data/wellfound_companies.csv / raw dump JSON       │
                   └──────────────────────────────────────────────────────┘
```

---

## 2. Subsystem Deep Dives

### Subsystem 1: Unified CLI Runner (`scraper.py`)

- **File**: [`scraper.py`](scraper.py)
- **Role**: Single entrypoint providing unified CLI dispatch across all scrapers, harvesters, and diagnostics.
- **Workflow**:
  1. Inspects `sys.argv[0]` to route to the appropriate engine:
     - `python scraper.py naukri ...` or `python scraper.py ...` -> Launches Naukri CLI.
     - `python scraper.py wellfound ...` -> Launches Wellfound CLI.
     - `python scraper.py emails ...` -> Launches Sourcing Agent & Email Harvester.
     - `python scraper.py test [inc42|ambitionbox]` -> Runs isolated diagnostic benchmarks.
  2. Sets UTF-8 encoding on Windows consoles to prevent `UnicodeEncodeError` when dealing with non-ASCII job titles or symbols.
  3. Preserves backward compatibility with legacy scripts and existing GitHub Actions workflows.

---

### Subsystem 2: Naukri Scraping Engine

#### A. XML Sitemap Streamer (`naukri_scraper/scraper.py`)
- **Mode**: Ultra-fast, zero-browser streaming decompression.
- **Execution Flow**:
  1. Reads the root XML sitemap index: `https://www.naukri.com/sitemap/sitemap.xml`.
  2. Selects matching city and skill sub-sitemaps (e.g. `sitemap-jobs-in-bangalore.xml.gz`).
  3. Downloads gzip compressed XML chunks in memory using streaming HTTP requests.
  4. Parses job URLs and decodes metadata directly from URL slug structures via [`parser.py`](naukri_scraper/parser.py):
     `job-listings-<title>-<company>-<location>-<exp_min>-to-<exp_max>-years-<job_id>`
  5. Applies keyword, location, experience, and timestamp filters in Python memory at thousands of jobs per second without opening a browser.

#### B. Playwright Multi-Tab Search Runner (`naukri_scraper/browser_scraper.py`)
- **Mode**: Headless Chromium browser automation.
- **Execution Flow**:
  1. Activates when custom search URLs (e.g. `https://www.naukri.com/jobs-in-india?jobAge=1`) are specified.
  2. Launches Chromium with automatic local browser fallback (`msedge` -> `chrome` -> bundled chromium).
  3. Bypasses bot detection by disabling `navigator.webdriver` and injecting authentic desktop user-agents.
  4. Intercepts Naukri's background AJAX API responses (`/jobapi/v3/search`) to capture structured JSON job cards.
  5. Concurrently processes pagination pages, collecting job titles, company names, experience, locations, posted dates, skills, and AmbitionBox profile IDs.

---

### Subsystem 3: Wellfound Scraping Engine

- **Files**: [`wellfound_scraper.py`](naukri_scraper/wellfound_scraper.py), [`wellfound_cli.py`](naukri_scraper/wellfound_cli.py)
- **Architecture**: **Dump & Filter** approach designed to overcome SPA rate limits and infinite scroll pagination locks.
- **Execution Flow**:
  1. Navigates to the search or location URL (e.g. `https://wellfound.com/location/bangalore`).
  2. Attaches Playwright network listeners to sniff GraphQL responses containing startup cards.
  3. Saves the full intercepted JSON payload to `--raw-dump` if requested.
  4. Parses each job posting and evaluates relative posted ages:
     - Handles expressions like `"1 hour ago"`, `"3 hours ago"`, `"yesterday"`, `"2 days ago"`, `"1 week ago"`, `"1 month ago"`.
     - Filters strictly against user thresholds (`--hours <N>` or `--days <N>`).
  5. Aggregates all open roles under their parent company: combines job titles, URLs, salary bands, equity ranges, and hiring stages.
  6. Automatically invokes the 4-Tier enrichment engine to resolve official company websites and LinkedIn profile URLs.

---

### Subsystem 4: 4-Tier Company Verification & Enrichment

To ensure high-fidelity company website resolution without hard dependency on any single third-party service, the system runs a tiered cascade:

```text
Company Name ──► [ Tier 0: Inc42 ] ──(found)──► Resolved (Website, Funding, Stage)
                       │ (not found)
                       ▼
                 [ Tier 1: AmbitionBox ] ──(found)──► Resolved (Website, Rating, Reviews)
                       │ (not found)
                       ▼
                 [ Tier 2: DuckDuckGo ] ──(found)──► Resolved (Official Web Domain)
                       │ (not found)
                       ▼
                 [ Tier 3: Clearbit ] ──(found)──► Resolved (Corporate Domain)
```

1. **Tier 0: Inc42 Scraper ([`inc42_scraper.py`](naukri_scraper/inc42_scraper.py))**:
   - Zero browser overhead (pure HTTP `requests`).
   - Normalizes startup slug variations (`zepto` -> `zepto-india`, `tigi-hr` -> `tigi-hr-management`).
   - Extracts website, founding year, founders, funding stage, total capital raised, and headquarters.
2. **Tier 1: AmbitionBox Scraper ([`browser_scraper.py`](naukri_scraper/browser_scraper.py))**:
   - Scrapes AmbitionBox company overview pages linked in Naukri cards.
   - Extracts official corporate website, employee review count, company rating, and office locations.
3. **Tier 2: DuckDuckGo Search (`ddgs`)**:
   - Executes search queries: `"<Company Name>" official website`
   - Strips job boards, social media, and directories to isolate the direct canonical company domain.
4. **Tier 3: Clearbit Autocomplete API**:
   - Queries `https://autocomplete.clearbit.com/v1/companies/suggest?query=<name>`.
   - Resolves domain names for startups and global corporations.

---

### Subsystem 5: Data Normalization & Export Pipelines

- **Files**: [`exporter.py`](naukri_scraper/exporter.py), [`config.py`](naukri_scraper/config.py)
- **Aggregation Logic**:
  - Groups individual job postings under a unique company row.
  - De-duplicates skills, locations, salaries, and experience ranges into formatted pipes (` | `) or comma lists.
  - Sorts companies by total open hiring volume (`total_jobs_posted DESC`).
- **Output Formats**:
  - Clean CSV formatted for spreadsheets, outreach, or CRM imports.
  - JSON dump format for programmatic consumption.

---

### Subsystem 6: Test Infrastructure & CI/CD

- **Test Suite**: [`tests/`](tests/)
  - **31 tests across 10 test files**:
    - `test_data_pipeline_dump.py`: Raw job dumps, 100% field presence across all 3 schema contracts (3 tests).
    - `test_inc42.py`: Slug normalization & mock HTML parsing (2 tests).
    - `test_ambitionbox.py`: AmbitionBox parsing with mock HTML (1 test).
    - `test_parser.py`: URL slug decoding, keyword, location, experience, and date filtering (6 tests).
    - `test_wellfound.py`: Relative age parsing (hours/days), company name cleaning, aggregation (3 tests).
    - `test_cli.py` & `test_scraper_cli.py`: Command line arguments, defaults, help flags across all subcommands (5 tests).
    - `test_exporter.py`: Company aggregation, CSV & JSON writing (2 tests).
    - `test_config.py`: URL and field dictionary completeness (4 tests).
    - `test_naukri_scraper.py`: Sitemap streaming & gzip decompression (5 tests).
  - **Execution Time**: All **31 tests execute in ~3.9 seconds**.
- **GitHub Actions Workflows**: [`.github/workflows/`](.github/workflows/)
  - `naukri_scraper.yml` (Scheduled / dispatch Naukri scraping)
  - `wellfound_scraper.yml` (Scheduled / dispatch Wellfound scraping)
  - `test_ambitionbox.yml` (AmbitionBox diagnostic runner)
  - `test_inc42.yml` (Inc42 startup verification runner)
  - Every workflow runs `python -m pytest tests/ -v` before executing any job scraping tasks.

---

## 3. Data Contracts & Schemas

### 1. `JOB_FIELDS` (26 Attributes)
Defined in [`naukri_scraper/config.py`](naukri_scraper/config.py):
```python
JOB_FIELDS = [
    "job_id", "job_title", "company_name", "company_website", "company_linkedin",
    "ambition_box_url", "experience_required", "salary", "locations", "job_description",
    "skills", "posted_date", "job_url", "company_rating", "company_reviews_count",
    "headquarters", "founders", "founding_year", "company_stage", "total_funding",
    "revenue", "scraped_at", "search_keyword", "search_location", "source", "source_url"
]
```

### 2. `COMPANY_FIELDS` (20 Attributes)
Defined in [`naukri_scraper/config.py`](naukri_scraper/config.py):
```python
COMPANY_FIELDS = [
    "company_name", "company_website", "company_linkedin", "total_jobs_posted",
    "job_titles", "naukri_job_urls", "locations", "experience_required",
    "top_skills", "salaries_disclosed", "company_rating", "company_reviews_count",
    "ambition_box_url", "latest_posted_date", "headquarters", "founders",
    "founding_year", "company_stage", "total_funding", "revenue"
]
```

### 3. `WELLFOUND_COMPANY_FIELDS` (12 Attributes)
Defined in [`naukri_scraper/wellfound_cli.py`](naukri_scraper/wellfound_cli.py):
```python
WELLFOUND_COMPANY_FIELDS = [
    "company_name", "company_website", "company_linkedin_url", "total_jobs_posted",
    "job_titles", "posted_dates", "wellfound_job_urls", "locations",
    "salaries", "equity", "stage", "employee_count"
]
```

---

## 4. Python Review Report (`/python-review`)

### A. Static Analysis & Linting
- **Tool**: `ruff check .`
- **Result**: **All checks passed! 0 errors, 0 warnings.**
- Clean imports, formatted code, and no extraneous f-strings or dead variables.

### B. Security & Vulnerability Audit
| Security Check | Status | Verification Detail |
|---|---|---|
| **Hardcoded Secrets** | **PASSED** | No API keys, passwords, or tokens in source code. All external keys use `os.getenv()`. |
| **SQL / Command Injection** | **PASSED** | No raw SQL queries or dynamic shell interpolation (`subprocess.run` uses safe list args without `shell=True`). |
| **Safe Deserialization** | **PASSED** | No `pickle.loads` or unsafe YAML parsing; standard `json.loads` and `json.dump` used throughout. |
| **Network & SSL Safety** | **PASSED** | HTTPS connections with bounded timeouts (4-10s) prevent indefinite process hangs. |
| **Sensitive Data Exposure** | **PASSED** | Error logs and exceptions capture high-level error context without leaking local filesystem paths or auth tokens. |

### C. Concurrency & Thread Safety
- **Wellfound & Naukri Parallelism**: Browser instances operate in separate isolated contexts with individual worker IDs.
- **Async Enrichment**: Inc42 and HTTP lookups run bounded async/thread pools with concurrency limits to respect rate limits.

### D. Immutability & Pythonic Idioms
- **Parsing & Filtering**: Filtering functions in `parser.py` take inputs and return new dictionaries and filtered lists without mutating input arguments in place.
- **Dictionary Lookups**: Safe `.get()` access with explicit defaults throughout to guard against `KeyError` on unexpected external HTML/JSON changes.
- **Context Managers**: File I/O operations (`open(...)`, `gzip.GzipFile`) use `with` statements ensuring file descriptors are closed promptly.

---

## 5. CLI Commands Quick Reference

```bash
# 1. Naukri Scraper (Sitemap Stream)
python scraper.py --keywords python devops --location Bangalore --experience 3 --hours 24

# 2. Naukri Scraper (Custom Playwright Search URL)
python scraper.py --url "https://www.naukri.com/jobs-in-india?functionAreaIdGid=4&functionAreaIdGid=5&jobAge=1" --pages 5 --output data/naukri_companies.csv

# 3. Wellfound Scraper (7-day startup filter)
python scraper.py wellfound --url "https://wellfound.com/location/bangalore" --days 7 --output data/wellfound_companies.csv

# 4. Diagnostic Benchmarks
python scraper.py test inc42 --company "Zepto"
python scraper.py test ambitionbox --url "https://www.ambitionbox.com/overview/tcs-overview"

# 5. Run Full Test Suite
python -m pytest tests/ -v
```
