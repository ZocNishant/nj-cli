from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from nj.models.config import VisaConfig
from nj.models.job import VisaLabel
from nj.scrapers.indeed import AdzunaScraper, IndeedScraper

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "adzuna_response.json").read_text()
)

ADZUNA_PAGE_URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"


@pytest.fixture
def scraper() -> AdzunaScraper:
    return AdzunaScraper(
        app_id="test-id",
        app_key="test-key",
        visa_config=VisaConfig(),
    )


@respx.mock
def test_scraper_returns_jobs_from_fixture(scraper: AdzunaScraper) -> None:
    respx.get(ADZUNA_PAGE_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    jobs = scraper._fetch_page("ML Engineer", "United States", 1)
    assert len(jobs) == 3
    titles = {j.title for j in jobs}
    assert "Machine Learning Engineer" in titles
    assert "Computer Vision Engineer" in titles
    assert "AI Researcher" in titles


def test_salary_formatted_correctly(scraper: AdzunaScraper) -> None:
    result = {
        "title": "ML Engineer",
        "company": {"display_name": "Acme"},
        "redirect_url": "https://example.com/job/1",
        "description": "ML role with H1B sponsorship",
        "location": {"display_name": "Remote"},
        "salary_min": 140000,
        "salary_max": 180000,
    }
    job = scraper._parse_result(result)
    assert job is not None
    assert job.salary_raw == "$140,000 - $180,000"


def test_visa_filter_applied(scraper: AdzunaScraper) -> None:
    results = FIXTURE["results"]
    jobs = [scraper._parse_result(r) for r in results]
    jobs = [j for j in jobs if j is not None]

    ml_job = next(j for j in jobs if j.title == "Machine Learning Engineer")
    cv_job = next(j for j in jobs if j.title == "Computer Vision Engineer")

    assert ml_job.visa_label == VisaLabel.CONFIRMED
    assert cv_job.visa_label == VisaLabel.BLOCKED


def test_empty_credentials_returns_empty_list() -> None:
    scraper = AdzunaScraper(
        app_id="",
        app_key="",
        visa_config=VisaConfig(),
    )
    jobs = scraper.scrape(["ML Engineer"])
    assert jobs == []


def test_job_id_deterministic(scraper: AdzunaScraper) -> None:
    result = FIXTURE["results"][0]
    job_a = scraper._parse_result(result)
    job_b = scraper._parse_result(result)
    assert job_a is not None and job_b is not None
    assert job_a.id == job_b.id


@respx.mock
def test_scraper_returns_empty_on_network_error(scraper: AdzunaScraper) -> None:
    respx.get(ADZUNA_PAGE_URL).mock(side_effect=httpx.ConnectError("timeout"))
    jobs = scraper._scrape_role("ML Engineer", "United States")
    assert jobs == []


def test_indeedscraper_alias_works() -> None:
    assert IndeedScraper is AdzunaScraper
