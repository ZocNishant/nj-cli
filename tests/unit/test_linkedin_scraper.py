from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nj.applying.anti_bot import RateLimiter
from nj.models.config import VisaConfig
from nj.scrapers.linkedin import LinkedInScraper


def make_scraper() -> LinkedInScraper:
    return LinkedInScraper(
        session_cookie="fake-cookie",
        visa_config=VisaConfig(),
        headless=True,
    )


def test_linkedin_scraper_name() -> None:
    assert make_scraper().name() == "linkedin"


def test_linkedin_returns_empty_on_playwright_import_error() -> None:
    scraper = make_scraper()
    with patch(
        "nj.scrapers.linkedin.asyncio.run",
        side_effect=ImportError("playwright not installed"),
    ):
        result = scraper.scrape(["ML Engineer"])
    assert result == []


def test_linkedin_returns_empty_on_fatal_error() -> None:
    scraper = make_scraper()
    with patch(
        "nj.scrapers.linkedin.asyncio.run",
        side_effect=Exception("network error"),
    ):
        result = scraper.scrape(["ML Engineer"])
    assert result == []


def test_is_blocked_detects_checkpoint_url() -> None:
    scraper = make_scraper()
    mock_page = MagicMock()
    mock_page.url = "https://www.linkedin.com/checkpoint/challenge"
    mock_page.query_selector = AsyncMock(return_value=None)
    result = asyncio.run(scraper._is_blocked(mock_page))
    assert result is True


def test_is_blocked_false_on_normal_url() -> None:
    scraper = make_scraper()
    mock_page = MagicMock()
    mock_page.url = "https://www.linkedin.com/jobs/view/123"
    mock_page.query_selector = AsyncMock(return_value=None)
    result = asyncio.run(scraper._is_blocked(mock_page))
    assert result is False


def test_rate_limiter_can_apply_when_under_limit() -> None:
    assert RateLimiter(max_per_day=5).can_apply() is True


def test_rate_limiter_cannot_apply_when_at_limit() -> None:
    rl = RateLimiter(max_per_day=2)
    rl.record_application()
    rl.record_application()
    assert rl.can_apply() is False


def test_rate_limiter_remaining_decrements() -> None:
    rl = RateLimiter(max_per_day=5)
    assert rl.remaining_today() == 5
    rl.record_application()
    assert rl.remaining_today() == 4


def test_rate_limiter_remaining_never_negative() -> None:
    rl = RateLimiter(max_per_day=1)
    rl.record_application()
    rl.record_application()
    assert rl.remaining_today() == 0


@pytest.mark.asyncio
async def test_rate_limiter_wait_completes() -> None:
    rl = RateLimiter(delay_min=0, delay_max=0)
    await rl.wait()


def test_rate_limiter_counts_from_db_when_repo_given():
    """The daily cap must survive a process restart, or `nj run` x3 sends 3x."""

    class FakeRepo:
        def __init__(self, n):
            self.n = n

        def count_today(self):
            return self.n

    assert RateLimiter(max_per_day=5, repo=FakeRepo(4)).can_apply() is True
    assert RateLimiter(max_per_day=5, repo=FakeRepo(5)).can_apply() is False
    assert RateLimiter(max_per_day=5, repo=FakeRepo(2)).remaining_today() == 3


def test_rate_limiter_fails_closed_if_the_count_errors():
    """A DB failure must not read as 'zero sent today'."""

    class BrokenRepo:
        def count_today(self):
            raise RuntimeError("db gone")

    assert RateLimiter(max_per_day=5, repo=BrokenRepo()).can_apply() is False
