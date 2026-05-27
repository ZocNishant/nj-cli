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
def test_scraper_returns_jobs(scraper: AdzunaScraper) -> None:
    respx.get(ADZUNA_PAGE_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    jobs = scraper._fetch_page("ML Engineer", "United States", 1)
    assert len(jobs) == 3


def test_visa_confirmed_job(scraper: AdzunaScraper) -> None:
    job = scraper._parse_result(FIXTURE["results"][0])
    assert job is not None
    assert job.visa_label == VisaLabel.CONFIRMED


def test_visa_blocked_job(scraper: AdzunaScraper) -> None:
    job = scraper._parse_result(FIXTURE["results"][1])
    assert job is not None
    assert job.visa_label == VisaLabel.BLOCKED


def test_job_id_is_deterministic(scraper: AdzunaScraper) -> None:
    job_a = scraper._parse_result(FIXTURE["results"][0])
    job_b = scraper._parse_result(FIXTURE["results"][0])
    assert job_a is not None and job_b is not None
    assert job_a.id == job_b.id


def test_indeedscraper_alias(scraper: AdzunaScraper) -> None:
    assert IndeedScraper is AdzunaScraper
    assert scraper.name() == "adzuna"
