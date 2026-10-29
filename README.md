# 🚀 Job Scraper Suite (Naukri, Wellfound & LinkedIn)

A production-grade, anti-bot resilient scraping and company enrichment system for **[Naukri.com](https://www.naukri.com)**, **[Wellfound.com](https://wellfound.com)**, and **[LinkedIn](https://www.linkedin.com)** with multi-tier corporate verification via **Inc42**, **AmbitionBox**, and **Clearbit**.

> 📖 **Architecture & Deep Dive Documentation**: See [ARCHITECTURE.md](ARCHITECTURE.md) for full subsystem breakdowns, data contracts, and technical review.

---

## 📁 Streamlined Project Structure

```text
├── .github/workflows/         # Automated GitHub Actions
│   ├── lead_generation.yml    # Automated daily B2B lead generation & email verification
│   ├── naukri_scraper.yml     # Automated daily & dispatch Naukri scraper + TDD test gate
│   ├── wellfound_scraper.yml  # Wellfound scraper (Dump & Filter) + TDD test gate
│   ├── test_ambitionbox.yml   # AmbitionBox diagnostic & live extraction
│   └── test_inc42.yml         # Inc42 startup & corporate enrichment benchmark
├── data/                      # Designated directory for scraped CSVs and JSONs (gitignored)
│   └── .gitkeep
├── naukri_scraper/            # Core package
│   ├── __init__.py
│   ├── browser_scraper.py     # Playwright multi-tab browser scraper & live enrichment
│   ├── cli.py                 # Naukri CLI entrypoint
│   ├── config.py              # Constants, schemas, and city mappings
│   ├── exporter.py            # CSV/JSON exporters and company aggregators
│   ├── inc42_scraper.py       # Inc42 fast async corporate & startup enrichment
│   ├── lead_cli.py            # B2B Lead Generation CLI entrypoint
│   ├── lead_enricher.py       # DoH MX verifier, contact crawler & email permutation engine
│   ├── linkedin_cli.py        # LinkedIn CLI entrypoint
│   ├── linkedin_scraper.py    # LinkedIn Guest API & browser scraper with date limits
│   ├── parser.py              # Sitemap XML & URL pattern parser
│   ├── scraper.py             # High-speed XML sitemap stream scraper
│   ├── wellfound_cli.py       # Wellfound CLI entrypoint
│   └── wellfound_scraper.py   # Wellfound browser scraper & filter engine
├── tests/                     # TDD Pytest Suite & Diagnostic Runners
│   ├── test_ambitionbox.py    # AmbitionBox tests & CLI runner
│   ├── test_cli.py            # CLI argument parser tests
│   ├── test_config.py         # Config constants & field validation
│   ├── test_data_pipeline_dump.py # Full schema & dump verification tests
│   ├── test_exporter.py       # Aggregator & exporter tests
│   ├── test_inc42.py          # Inc42 parser tests & benchmark runner
│   ├── test_lead_enricher.py  # DoH MX, contact crawl & permutation tests
│   ├── test_linkedin.py       # LinkedIn card parser, date limit & pagination tests
│   ├── test_naukri_scraper.py # Sitemap decompression & stream tests
│   ├── test_parser.py         # URL parsing & filter tests
│   ├── test_scraper_cli.py    # Unified top-level runner tests
│   └── test_wellfound.py      # Age parsing & Wellfound aggregation tests
├── scratch/                   # Experimental / scratch scripts (gitignored)
├── scraper.py                 # Unified top-level CLI runner
├── requirements.txt           # Consolidated project dependencies
└── README.md                  # Complete documentation
```

---

## ⚡ Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/Rohanpatel16/naukri-scraper.git
cd naukri-scraper

# Install dependencies (core + testing)
pip install -r requirements.txt

# Install Playwright browser dependencies (for browser-based scraping)
python -m playwright install chromium
```

### 2. Run the Test Suite (TDD Verified)

```bash
python -m pytest tests/ -v
```

All unit tests verify schema consistency, age filtering, URL decoding, aggregation logic, and CLI dispatch.

---

## 💻 Unified CLI Usage (`scraper.py`)

The unified top-level runner [`scraper.py`](file:///d:/Codinf%20projets/Naukri.com%20scraper/scraper.py) provides access to all scrapers and diagnostic tools.

### 🔷 1. Naukri Scraper

#### Fast XML Sitemap Stream (No Browser Required):
```bash
python scraper.py --keywords python devops --location Bangalore --experience 3 --hours 24
```

#### Custom Filter Search URL (Playwright Multi-Tab):
```bash
python scraper.py --url "https://www.naukri.com/jobs-in-india?functionAreaIdGid=4&functionAreaIdGid=5&jobAge=1" --pages 5 --output data/naukri_companies.csv
```

#### Strict Inc42 Verification Only:
```bash
python scraper.py --url "https://www.naukri.com/jobs-in-india?jobAge=1" --inc42-only
```

---

### 🔶 2. Wellfound Scraper (Dump & Filter)

Scrape jobs and startup profiles from Wellfound:

```bash
# Scrape software engineering jobs in India posted in last 7 days
python scraper.py wellfound --url "https://wellfound.com/role/l/software-engineer/india" --days 7 --output data/wellfound_companies.csv
```

```bash
# Filter jobs posted in last 24 hours with 4 parallel browser workers
python scraper.py wellfound --url "https://wellfound.com/jobs?locations=India" --hours 24 --workers 4
```

---

### 💼 3. LinkedIn Scraper (Fast Guest API & Browser Fallback)

Scrape jobs and enterprise hiring data from LinkedIn with **two-tier date limit filtering**:

```bash
# Scrape Python developer jobs in India posted in last 3 days
python scraper.py linkedin --keywords "python developer" --location "India" --days 3 --max-jobs 50

# Scrape DevOps roles in Bangalore posted in the last 24 hours
python scraper.py linkedin --keywords "devops" --location "Bangalore" --hours 24 --max-jobs 25

# Scrape from a custom LinkedIn search URL using Playwright browser
python scraper.py linkedin --url "https://www.linkedin.com/jobs/search?keywords=React&location=India" --browser
```

---

### 🎯 4. Automated B2B Lead Generation Engine

Transform raw job postings and corporate profiles into **verified, deliverable B2B leads** with **zero new dependencies** and **100% runnable in GitHub Actions**:

- **DoH MX Inbound Verification**: Queries Cloudflare & Google DNS-over-HTTPS (port 443) to verify active email hosting (Google Workspace, Microsoft 365, Zoho) with zero blocked port 25 timeouts.
- **Targeted Public Crawl**: Discovers direct team emails from `/contact`, `/about`, `/team`, `/privacy-policy` (GDPR mandatory DPO emails), and `/.well-known/security.txt`.
- **Decision-Maker Permutations**: Generates verified candidate email formats (`first@domain`, `first.last@domain`, `f.last@domain`) for founders and leadership.
- **Hiring Intent Signals**: Automatically categorizes open positions into high-converting sales triggers (*AI & Machine Learning*, *Cloud & Infrastructure*, *Sales & GTM Growth*).

```bash
# 1. Direct domain inspection & founder permutations
python scraper.py leads --domain razorpay.com --founders "Harshil Mathur, Shashank Kumar"

# 2. Enrich scraped company list into verified leads
python scraper.py leads -i data/naukri_companies.csv -o data/leads.csv

# 3. End-to-end scrape + lead generation in one command
python scraper.py --keywords "python devops" --location Bangalore --leads --leads-output data/leads.csv
```

---

### 🛠 5. Diagnostic & Verification Tools

Run instant extraction benchmarks on any company or profile:

```bash
# Test Inc42 corporate & startup extraction
python scraper.py test inc42 --company "CRED"

# Test AmbitionBox live extraction
python scraper.py test ambitionbox --url "https://www.ambitionbox.com/overview/tcs-overview"
```

---

## 🔍 Data Enrichment Pipeline

When scraping Naukri or Wellfound, companies undergo multi-tier automated enrichment:

1. **Inc42 Datalabs (Tier 0)**: Direct slug generation & fast async parsing for Indian tech startups (official website, LinkedIn, founders, founding year, funding stage, total funding, revenue).
2. **AmbitionBox (Tier 1)**: Concurrent browser tabs extracting ratings, employee counts, industry tags, and websites.
3. **DuckDuckGo Search (Tier 2)**: Targeted domain searches for unlisted or custom corporate names.
4. **Clearbit Autocomplete (Tier 3)**: Fast API lookup for corporate domain names.
5. **DoH & Public Crawler (Lead Tier)**: Port-443 MX validation, targeted contact crawl, email permutations, and hiring intent tagging.

---

## 🤖 GitHub Actions Automation

Automated scheduled workflows are configured in `.github/workflows/`:

| Workflow | Triggers | Description |
| :--- | :--- | :--- |
| **`B2B Lead Generation Engine`** | Daily at `07:00 UTC` / Manual Dispatch | Scrapes target roles, verifies MX inboxes over DoH, crawls contacts, and uploads `data/leads.csv`. |
| **`Naukri Job Scraper`** | Daily at `06:00 UTC` / Manual Dispatch | Runs automated test gate, scrapes Naukri, enriches companies, and uploads CSV artifacts. |
| **`Wellfound Job Scraper`** | Manual Dispatch | Runs test gate, performs Dump & Filter scraping on Wellfound, and exports enriched CSVs. |
| **`Test AmbitionBox`** | Manual Dispatch | Diagnostic testing for AmbitionBox parsing. |
| **`Test Inc42`** | Manual Dispatch | Benchmark extraction test for Indian startup profiles on Inc42. |

All workflow runs enforce the **TDD test gate (`pytest tests/`)** before executing scrapers.