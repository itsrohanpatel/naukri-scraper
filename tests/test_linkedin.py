"""Unit tests for the LinkedIn job scraper module."""

from bs4 import BeautifulSoup

from naukri_scraper.linkedin_cli import parse_args
from naukri_scraper.linkedin_scraper import (
    LinkedInScraper,
    parse_linkedin_posted_age_days,
    parse_linkedin_card_html,
)

SAMPLE_CARD_HTML = """
<li class="base-card relative w-full hover:no-underline focus:no-underline base-card--link base-search-card base-search-card--link job-search-card">
    <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2]" href="https://in.linkedin.com/jobs/view/senior-python-developer-at-swiggy-4123456789?position=1&amp;pageNum=0">
        <span class="sr-only">Senior Python Developer</span>
    </a>
    <div class="base-search-card__info">
        <h3 class="base-search-card__title">Senior Python Developer</h3>
        <h4 class="base-search-card__subtitle">
            <a class="hidden-nested-link" href="https://in.linkedin.com/company/swiggy-in">Swiggy</a>
        </h4>
        <div class="base-search-card__metadata">
            <span class="job-search-card__location">Bengaluru, Karnataka, India</span>
            <time class="job-search-card__listdate" datetime="2026-09-04">2 days ago</time>
        </div>
    </div>
</li>
"""


def test_parse_linkedin_posted_age_days():
    assert parse_linkedin_posted_age_days("Just now") == 0.0
    assert parse_linkedin_posted_age_days("today") == 0.0
    assert parse_linkedin_posted_age_days("yesterday") == 1.0
    assert abs(parse_linkedin_posted_age_days("12 hours ago") - 0.5) < 0.01
    assert parse_linkedin_posted_age_days("3 days ago") == 3.0
    assert parse_linkedin_posted_age_days("2 weeks ago") == 14.0
    assert parse_linkedin_posted_age_days("1 month ago") == 30.0


def test_parse_linkedin_card_html():
    soup = BeautifulSoup(SAMPLE_CARD_HTML, "html.parser")
    card_li = soup.find("li")
    job = parse_linkedin_card_html(card_li)

    assert job is not None
    assert job["title"] == "Senior Python Developer"
    assert job["company"] == "Swiggy"
    assert "Bengaluru" in job["location"]
    assert job["posted_date"] == "2026-09-04"
    assert job["age_days"] == 2.0
    assert "linkedin.com/jobs/view/" in job["url"]
    assert job["source"] == "linkedin"
    assert job["company_linkedin"] == "https://in.linkedin.com/company/swiggy-in"


def test_linkedin_cli_args_defaults():
    args = parse_args(["-k", "python"])
    assert args.keywords == ["python"]
    assert args.location is None
    assert args.days is None
    assert args.hours is None
    assert args.max_jobs == 50
    assert args.output == "data/linkedin_companies.csv"
    assert not args.browser


def test_linkedin_cli_args_custom():
    args = parse_args([
        "-k", "golang", "microservices",
        "-l", "Bangalore",
        "-D", "3",
        "-H", "48",
        "-n", "100",
        "-o", "custom_linkedin.csv",
        "--browser",
    ])
    assert args.keywords == ["golang", "microservices"]
    assert args.location == "Bangalore"
    assert args.days == 3
    assert args.hours == 48
    assert args.max_jobs == 100
    assert args.output == "custom_linkedin.csv"
    assert args.browser is True


def test_linkedin_calculate_f_tpr_param():
    scraper = LinkedInScraper()
    assert scraper.get_f_tpr_seconds(hours=24) == 86400
    assert scraper.get_f_tpr_seconds(days=7) == 604800
    assert scraper.get_f_tpr_seconds(days=1) == 86400
    assert scraper.get_f_tpr_seconds(hours=12) == 43200
    assert scraper.get_f_tpr_seconds(days=None, hours=None) is None
