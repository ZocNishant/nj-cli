from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from nj.models.config import VisaConfig
from nj.models.job import VisaLabel
from nj.scrapers.indeed import IndeedScraper

FIXTURE_HTML = (Path(__file__).parent.parent / "fixtures" / "indeed_jobs.html").read_text()


@pytest.fixture
def scraper() -> IndeedScraper:
    return IndeedScraper(VisaConfig())


def test_scraper_returns_two_jobs(scraper: IndeedScraper) -> None:
    jobs = scraper._parse_html(FIXTURE_HTML)
    assert len(jobs) == 2


def test_first_job_visa_confirmed(scraper: IndeedScraper) -> None:
    jobs = scraper._parse_html(FIXTURE_HTML)
    ml_job = next(j for j in jobs if j.title == "ML Engineer")
    assert ml_job.visa_label == VisaLabel.CONFIRMED


def test_second_job_visa_blocked(scraper: IndeedScraper) -> None:
    jobs = scraper._parse_html(FIXTURE_HTML)
    cv_job = next(j for j in jobs if j.title == "Computer Vision Engineer")
    assert cv_job.visa_label == VisaLabel.BLOCKED


def test_job_id_is_deterministic(scraper: IndeedScraper) -> None:
    jobs_first = scraper._parse_html(FIXTURE_HTML)
    jobs_second = scraper._parse_html(FIXTURE_HTML)
    assert jobs_first[0].id == jobs_second[0].id
    assert jobs_first[1].id == jobs_second[1].id


def test_scraper_returns_empty_on_playwright_error(scraper: IndeedScraper) -> None:
    with patch("nj.scrapers.indeed.asyncio.run", side_effect=Exception("playwright error")):
        jobs = scraper.scrape(["ML Engineer"], "United States")
    assert jobs == []
