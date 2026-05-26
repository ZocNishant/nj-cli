from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
import respx

from nj.models.config import VisaConfig
from nj.models.job import VisaLabel
from nj.scrapers.indeed import IndeedScraper

FIXTURE_XML = (Path(__file__).parent.parent / "fixtures" / "indeed_rss.xml").read_text()
INDEED_URL = re.compile(r"https://www\.indeed\.com/rss")


@pytest.fixture
def scraper() -> IndeedScraper:
    return IndeedScraper(VisaConfig())


def test_scraper_returns_two_jobs(scraper: IndeedScraper, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    with respx.mock:
        respx.get(INDEED_URL).mock(return_value=httpx.Response(200, text=FIXTURE_XML))
        jobs = scraper.scrape(["ML Engineer"], "United States")
    assert len(jobs) == 2


def test_first_job_visa_confirmed(scraper: IndeedScraper, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    with respx.mock:
        respx.get(INDEED_URL).mock(return_value=httpx.Response(200, text=FIXTURE_XML))
        jobs = scraper.scrape(["ML Engineer"], "United States")
    ml_job = next(j for j in jobs if j.title == "ML Engineer")
    assert ml_job.visa_label == VisaLabel.CONFIRMED


def test_second_job_visa_blocked(scraper: IndeedScraper, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    with respx.mock:
        respx.get(INDEED_URL).mock(return_value=httpx.Response(200, text=FIXTURE_XML))
        jobs = scraper.scrape(["ML Engineer"], "United States")
    cv_job = next(j for j in jobs if j.title == "Computer Vision Engineer")
    assert cv_job.visa_label == VisaLabel.BLOCKED


def test_job_id_is_deterministic(scraper: IndeedScraper, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    with respx.mock:
        respx.get(INDEED_URL).mock(return_value=httpx.Response(200, text=FIXTURE_XML))
        jobs_first = scraper.scrape(["ML Engineer"], "United States")
    with respx.mock:
        respx.get(INDEED_URL).mock(return_value=httpx.Response(200, text=FIXTURE_XML))
        jobs_second = scraper.scrape(["ML Engineer"], "United States")
    assert jobs_first[0].id == jobs_second[0].id
    assert jobs_first[1].id == jobs_second[1].id


def test_scraper_returns_empty_on_network_error(
    scraper: IndeedScraper, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    with respx.mock:
        respx.get(INDEED_URL).mock(side_effect=Exception("network error"))
        jobs = scraper.scrape(["ML Engineer"], "United States")
    assert jobs == []
