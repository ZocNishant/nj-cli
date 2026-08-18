from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
import respx

from nj.models.config import VisaConfig
from nj.models.job import VisaLabel
from nj.scrapers.remoteok import RemoteOKScraper

FIXTURE_JSON = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "remoteok_response.json").read_text()
)
REMOTEOK_URL = re.compile(r"https://remoteok\.com/api")


@pytest.fixture
def scraper() -> RemoteOKScraper:
    return RemoteOKScraper(VisaConfig())


def test_scraper_returns_ml_jobs(scraper: RemoteOKScraper, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    with respx.mock:
        respx.get(REMOTEOK_URL).mock(return_value=httpx.Response(200, json=FIXTURE_JSON))
        jobs = scraper.fetch(["ML Engineer"])
    assert len(jobs) > 0
    assert all(j.source == "remoteok" for j in jobs)


def test_scraper_filters_non_ml_jobs(scraper: RemoteOKScraper) -> None:
    non_ml_item = {
        "slug": "remote-frontend-dev",
        "company": "WebStartup",
        "position": "Frontend Developer",
        "description": "React frontend role.",
        "tags": ["javascript", "react", "frontend"],
        "location": "Remote",
    }
    result = scraper._parse_response([non_ml_item])
    assert result == []


def test_visa_confirmed_job(scraper: RemoteOKScraper) -> None:
    ml_item = {
        "slug": "remote-ml-engineer-techcorp",
        "company": "TechCorp",
        "position": "ML Engineer",
        "description": "H1B sponsorship available.",
        "tags": ["machine-learning", "python"],
        "location": "Remote",
    }
    jobs = scraper._parse_response([ml_item])
    assert len(jobs) == 1
    assert jobs[0].visa_label == VisaLabel.CONFIRMED


def test_scraper_returns_empty_on_network_error(
    scraper: RemoteOKScraper, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    with respx.mock:
        respx.get(REMOTEOK_URL).mock(side_effect=Exception("network error"))
        jobs = scraper.fetch(["ML Engineer"])
    assert jobs == []


def test_job_id_is_deterministic(scraper: RemoteOKScraper) -> None:
    item = {
        "slug": "remote-ml-engineer-techcorp",
        "company": "TechCorp",
        "position": "ML Engineer",
        "description": "ML job.",
        "tags": ["machine-learning"],
        "location": "Remote",
    }
    jobs1 = scraper._parse_response([item])
    jobs2 = scraper._parse_response([item])
    assert jobs1[0].id == jobs2[0].id
