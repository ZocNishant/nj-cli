"""Tests for async parallel scraping infrastructure."""
from __future__ import annotations

import asyncio
from datetime import datetime, UTC

import pytest

from nj.models.job import Job, VisaLabel, JobStatus
from nj.scrapers.base import BaseScraper


def make_job(job_id: str = "j1") -> Job:
    return Job(
        id=job_id,
        title="ML Engineer",
        company="Acme",
        url=f"https://example.com/{job_id}",
        description="PyTorch ML role. H1B sponsor.",
        location="Remote",
        source="remoteok",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash=job_id,
    )


class SyncScraper(BaseScraper):
    def __init__(self, name: str, jobs: list):
        self._name = name
        self._jobs = jobs

    def name(self) -> str:
        return self._name

    def scrape(self, roles, location) -> list:
        return self._jobs


class AsyncScraper(BaseScraper):
    def __init__(self, name: str, jobs: list):
        self._name = name
        self._jobs = jobs

    def name(self) -> str:
        return self._name

    async def scrape(self, roles, location) -> list:
        return self._jobs


class FailingScraper(BaseScraper):
    def name(self) -> str:
        return "failing"

    def scrape(self, roles, location) -> list:
        raise RuntimeError("Scraper failed")


@pytest.mark.asyncio
async def test_sync_scraper_runs_in_thread():
    import inspect
    scraper = SyncScraper("test", [make_job("j1")])
    assert not inspect.iscoroutinefunction(scraper.scrape)
    result = await asyncio.to_thread(scraper.scrape, ["ML Engineer"], "Remote")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_async_scraper_runs_directly():
    import inspect
    scraper = AsyncScraper("test", [make_job("j1")])
    assert inspect.iscoroutinefunction(scraper.scrape)
    result = await scraper.scrape(["ML Engineer"], "Remote")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_parallel_scrapers_all_run():
    scrapers = [
        SyncScraper("s1", [make_job("j1")]),
        SyncScraper("s2", [make_job("j2")]),
        SyncScraper("s3", [make_job("j3")]),
    ]

    async def scrape_one(s):
        import inspect
        if inspect.iscoroutinefunction(s.scrape):
            return s.name(), await s.scrape([], "")
        else:
            return s.name(), await asyncio.to_thread(s.scrape, [], "")

    results = await asyncio.gather(*[scrape_one(s) for s in scrapers])
    names = [r[0] for r in results]
    assert "s1" in names
    assert "s2" in names
    assert "s3" in names


@pytest.mark.asyncio
async def test_failing_scraper_doesnt_break_others():
    scrapers = [
        SyncScraper("good1", [make_job("j1")]),
        FailingScraper(),
        SyncScraper("good2", [make_job("j2")]),
    ]

    async def scrape_one(s):
        try:
            import inspect
            if inspect.iscoroutinefunction(s.scrape):
                jobs = await s.scrape([], "")
            else:
                jobs = await asyncio.to_thread(s.scrape, [], "")
            return s.name(), jobs
        except Exception:
            return s.name(), []

    results = await asyncio.gather(*[scrape_one(s) for s in scrapers])
    all_jobs = []
    for name, jobs in results:
        all_jobs.extend(jobs)
    assert len(all_jobs) == 2


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency():
    from asyncio import Semaphore

    sem = Semaphore(2)
    concurrent = 0
    max_concurrent = 0

    async def task():
        nonlocal concurrent, max_concurrent
        async with sem:
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            await asyncio.sleep(0.01)
            concurrent -= 1

    await asyncio.gather(*[task() for _ in range(10)])
    assert max_concurrent <= 2


@pytest.mark.asyncio
async def test_parallel_faster_than_sequential():
    import time

    async def slow_scrape():
        await asyncio.sleep(0.05)
        return [make_job()]

    t_start = time.monotonic()
    await asyncio.gather(*[slow_scrape() for _ in range(5)])
    parallel_time = time.monotonic() - t_start

    t_start = time.monotonic()
    for _ in range(5):
        await slow_scrape()
    sequential_time = time.monotonic() - t_start

    assert parallel_time < sequential_time * 0.6


def test_scraper_base_has_name_method():
    scraper = SyncScraper("test", [])
    assert scraper.name() == "test"
