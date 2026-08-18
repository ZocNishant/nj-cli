"""The scraper contract: async at the interface, blocking underneath.

`BaseScraper.scrape` used to be declared synchronous while both pipelines
branched on `inspect.iscoroutinefunction(scraper.scrape)` before falling back to
a thread. Every implementation was synchronous, so the async branch was dead
code and a new scraper author had no contract to follow. The interface is now
async for everyone; implementations supply blocking `fetch`.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from datetime import UTC, datetime

from nj.models.job import Job, JobStatus, VisaLabel
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


class BlockingScraper(BaseScraper):
    """The ordinary case: plain httpx-style blocking code."""

    def __init__(self, name: str, jobs: list, delay: float = 0.0):
        self._name = name
        self._jobs = jobs
        self._delay = delay
        self.seen_location: str | None = None

    def name(self) -> str:
        return self._name

    def fetch(self, roles, location="its-own-default") -> list:
        self.seen_location = location
        if self._delay:
            time.sleep(self._delay)
        return self._jobs


class NativelyAsyncScraper(BaseScraper):
    """A source that is genuinely async may override scrape directly."""

    def __init__(self, name: str, jobs: list):
        self._name = name
        self._jobs = jobs

    def name(self) -> str:
        return self._name

    def fetch(self, roles, location="") -> list:  # pragma: no cover - never called
        raise AssertionError("scrape() was overridden; fetch must not run")

    async def scrape(self, roles, location=None) -> list:
        await asyncio.sleep(0)
        return self._jobs


class FailingScraper(BaseScraper):
    def name(self) -> str:
        return "failing"

    def fetch(self, roles, location="") -> list:
        raise RuntimeError("Scraper failed")


async def test_scrape_is_awaitable_even_for_a_blocking_implementation() -> None:
    scraper = BlockingScraper("test", [make_job("j1")])
    assert inspect.iscoroutinefunction(scraper.scrape)
    assert len(await scraper.scrape(["ML Engineer"], "Remote")) == 1


async def test_an_implementation_may_override_scrape() -> None:
    scraper = NativelyAsyncScraper("test", [make_job("j1")])
    assert len(await scraper.scrape(["ML Engineer"], "Remote")) == 1


async def test_omitting_location_preserves_the_implementations_default() -> None:
    """RemoteOK defaults to 'Remote', Adzuna to 'United States'. Passing "" would
    silently override both."""
    scraper = BlockingScraper("test", [])
    await scraper.scrape(["ML Engineer"])
    assert scraper.seen_location == "its-own-default"

    await scraper.scrape(["ML Engineer"], "Berlin")
    assert scraper.seen_location == "Berlin"


async def test_blocking_fetches_do_not_serialise() -> None:
    """The point of the thread: one slow board must not hold up the rest."""
    scrapers = [BlockingScraper(f"s{i}", [make_job(f"j{i}")], delay=0.05) for i in range(5)]

    started = time.monotonic()
    await asyncio.gather(*[s.scrape([], "") for s in scrapers])
    parallel = time.monotonic() - started

    started = time.monotonic()
    for s in scrapers:
        await s.scrape([], "")
    sequential = time.monotonic() - started

    assert parallel < sequential * 0.6


async def test_a_failing_source_does_not_end_the_run() -> None:
    from nj.models.config import Config
    from nj.pipeline.ingest import IngestService

    class NullRepo:
        def existing_ids(self, ids):
            return set()

        def save_job(self, job):
            pass

    service = IngestService(
        Config(),
        NullRepo(),
        scrapers=[
            BlockingScraper("good1", [make_job("j1")]),
            FailingScraper(),
            BlockingScraper("good2", [make_job("j2")]),
        ],
    )
    results = await service.scrape()
    assert results["failing"] == []
    assert len(results["good1"]) == 1
    assert len(results["good2"]) == 1


def test_scrapers_report_a_name() -> None:
    assert BlockingScraper("test", []).name() == "test"


def test_every_shipped_scraper_implements_the_contract() -> None:
    """A source that forgets `fetch` must fail at import, not at 3am in a run."""
    from nj.scrapers.arbeitnow import ArbeitnowScraper
    from nj.scrapers.indeed import AdzunaScraper
    from nj.scrapers.jsearch import JSearchScraper
    from nj.scrapers.linkedin import LinkedInScraper
    from nj.scrapers.remoteok import RemoteOKScraper
    from nj.scrapers.usajobs import USAJobsScraper
    from nj.scrapers.weworkremotely import WeWorkRemotelyScraper

    for cls in (
        ArbeitnowScraper,
        AdzunaScraper,
        JSearchScraper,
        LinkedInScraper,
        RemoteOKScraper,
        USAJobsScraper,
        WeWorkRemotelyScraper,
    ):
        assert not inspect.isabstract(cls), f"{cls.__name__} does not implement fetch()"
        assert inspect.iscoroutinefunction(cls.scrape), f"{cls.__name__}.scrape is not async"
