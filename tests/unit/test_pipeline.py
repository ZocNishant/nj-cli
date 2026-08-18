"""The orchestration layer, tested without going through Typer.

This logic used to live inside two Typer callbacks, which is why cmd_run and
cmd_search sat at 23% and 20% coverage while the services they called averaged
above 90%. It is also why they drifted: concurrent scoring was added to one,
enrichment to the other, skip-reason recording to the other again.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta

from nj.models.config import Config
from nj.models.job import Job, VisaLabel
from nj.models.score import ScoreResult
from nj.pipeline import IngestService, ScoringService, build_scrapers
from nj.pipeline.scoring import concurrency_for
from nj.scrapers.base import BaseScraper

# Long enough to clear the ghost filter's "vague description" signal, which is
# what a real posting looks like.
REAL_DESCRIPTION = (
    "We are hiring a machine learning engineer to build and ship computer vision "
    "models in production. You will work with PyTorch, design training pipelines, "
    "evaluate models against held-out data, and collaborate with product teams on "
    "deployment. Requirements: 2+ years of experience with Python and deep learning "
    "frameworks, familiarity with cloud infrastructure, and strong communication. "
    "We offer competitive compensation, health insurance, and a remote-first culture."
)


def make_job(job_id="j1", company="Acme", title="ML Engineer", desc=REAL_DESCRIPTION, age_days=1):
    return Job(
        id=job_id,
        title=title,
        company=company,
        url=f"https://example.com/{job_id}",
        description=desc,
        location="Remote",
        source="test",
        visa_label=VisaLabel.UNKNOWN,
        scraped_at=datetime.now(UTC) - timedelta(days=age_days),
        description_hash=job_id,
    )


class StubScraper(BaseScraper):
    def __init__(self, name, jobs, delay=0.0, fail=False):
        self._name, self._jobs, self._delay, self._fail = name, jobs, delay, fail

    def name(self):
        return self._name

    def fetch(self, roles, location=""):
        if self._delay:
            time.sleep(self._delay)
        if self._fail:
            raise RuntimeError("board is down")
        return self._jobs


class FakeJobRepo:
    def __init__(self, existing=None):
        self.existing = set(existing or [])
        self.saved = []

    def existing_ids(self, ids):
        return {i for i in ids if i in self.existing}

    def save_job(self, job):
        self.saved.append(job)


# --- ingest ----------------------------------------------------------------


def test_collect_returns_new_jobs_and_stores_them() -> None:
    repo = FakeJobRepo()
    service = IngestService(Config(), repo, scrapers=[StubScraper("a", [make_job("j1")])])
    result = service.collect()
    assert [j.id for j in result.jobs] == ["j1"]
    assert [j.id for j in repo.saved] == ["j1"]


def test_collect_counts_per_source() -> None:
    service = IngestService(
        Config(),
        FakeJobRepo(),
        scrapers=[
            StubScraper("a", [make_job("j1"), make_job("j2")]),
            StubScraper("b", [make_job("j3")]),
        ],
    )
    result = service.collect()
    assert result.per_source == {"a": 2, "b": 1}
    assert result.scraped == 3
    assert "a=2" in result.sources_line


def test_collect_drops_jobs_already_stored() -> None:
    service = IngestService(
        Config(), FakeJobRepo(existing={"j1"}), scrapers=[StubScraper("a", [make_job("j1")])]
    )
    result = service.collect()
    assert result.jobs == []
    assert result.duplicates == 1


def test_collect_drops_ghosts_but_reports_them() -> None:
    fresh = make_job("fresh", age_days=1)
    stale = make_job("stale", age_days=200)
    service = IngestService(Config(), FakeJobRepo(), scrapers=[StubScraper("a", [fresh, stale])])
    result = service.collect()
    assert [j.id for j in result.jobs] == ["fresh"]
    assert len(result.ghosts) == 1


def test_a_dead_source_does_not_lose_the_others() -> None:
    service = IngestService(
        Config(),
        FakeJobRepo(),
        scrapers=[StubScraper("dead", [], fail=True), StubScraper("live", [make_job("j1")])],
    )
    result = service.collect()
    assert [j.id for j in result.jobs] == ["j1"]


def test_save_false_collects_without_writing() -> None:
    repo = FakeJobRepo()
    service = IngestService(Config(), repo, scrapers=[StubScraper("a", [make_job("j1")])])
    result = service.collect(save=False)
    assert result.jobs
    assert repo.saved == []


def test_sources_are_built_lazily_from_config() -> None:
    """Both commands duplicated this function, character-identical."""
    config = Config()
    config.scraper.remoteok_enabled = True
    config.scraper.weworkremotely_enabled = False
    config.scraper.arbeitnow_enabled = False
    names = [s.name() for s in build_scrapers(config)]
    assert "remoteok" in names


def test_no_credentials_still_yields_a_source() -> None:
    """Zero scrapers reads as 'nothing was posted', not 'you set no keys'."""
    config = Config()
    for field in ("remoteok", "weworkremotely", "arbeitnow", "adzuna", "jsearch", "usajobs"):
        setattr(config.scraper, f"{field}_enabled", False)
    assert len(build_scrapers(config)) == 1


def test_enrichment_failure_is_survivable() -> None:
    service = IngestService(Config(), FakeJobRepo(), scrapers=[])
    assert service.enrich([make_job()], {}, "/nonexistent/dir/nope.db") == {}


# --- scoring ---------------------------------------------------------------


def make_score(job_id="j1", total=70):
    return ScoreResult(
        job_id=job_id, total_score=total, confidence=0.8, scored_at=datetime.now(UTC)
    )


class RecordingProvider:
    """Tracks how many scorings overlap, to prove concurrency is real."""

    def __init__(self, delay=0.02):
        self.delay = delay
        self.active = 0
        self.peak = 0

    async def complete(self, request):  # pragma: no cover - patched out below
        raise AssertionError("score_job is patched in these tests")


def _service(monkeypatch, provider, handler, concurrency=None):
    async def fake_score_job(job, cv_base, config, provider, repo=None):
        return await handler(job)

    monkeypatch.setattr("nj.scoring.scorer.score_job", fake_score_job)
    return ScoringService(
        config=Config(),
        provider=provider,
        cv_base={},
        concurrency=concurrency,
    )


async def test_score_many_returns_a_result_per_job(monkeypatch) -> None:
    async def handler(job):
        return make_score(job.id)

    service = _service(monkeypatch, RecordingProvider(), handler)
    jobs = [make_job(f"j{i}") for i in range(4)]
    scored = await service.score_many(jobs)
    assert [j.id for j, _ in scored] == ["j0", "j1", "j2", "j3"]


async def test_scoring_actually_runs_concurrently(monkeypatch) -> None:
    """nj run scored serially — one asyncio.run per job — while nj search
    scored five at a time. Same work, several times slower."""
    provider = RecordingProvider()

    async def handler(job):
        provider.active += 1
        provider.peak = max(provider.peak, provider.active)
        await asyncio.sleep(0.02)
        provider.active -= 1
        return make_score(job.id)

    service = _service(monkeypatch, provider, handler, concurrency=5)
    await service.score_many([make_job(f"j{i}") for i in range(10)])
    assert provider.peak > 1


async def test_concurrency_is_capped(monkeypatch) -> None:
    provider = RecordingProvider()

    async def handler(job):
        provider.active += 1
        provider.peak = max(provider.peak, provider.active)
        await asyncio.sleep(0.01)
        provider.active -= 1
        return make_score(job.id)

    service = _service(monkeypatch, provider, handler, concurrency=2)
    await service.score_many([make_job(f"j{i}") for i in range(8)])
    assert provider.peak <= 2


async def test_one_unscoreable_job_does_not_lose_the_batch(monkeypatch) -> None:
    async def handler(job):
        if job.id == "j1":
            raise RuntimeError("model said no")
        return make_score(job.id)

    service = _service(monkeypatch, RecordingProvider(), handler)
    scored = await service.score_many([make_job("j0"), make_job("j1"), make_job("j2")])
    assert [j.id for j, _ in scored] == ["j0", "j2"]


async def test_rate_limits_are_retried(monkeypatch) -> None:
    attempts = {"n": 0}

    async def handler(job):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("429 Too Many Requests")
        return make_score(job.id)

    real_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda *_a, **_k: real_sleep(0))
    service = _service(monkeypatch, RecordingProvider(), handler)
    scored = await service.score_many([make_job("j0")])
    assert len(scored) == 1
    assert attempts["n"] == 2


async def test_progress_callback_fires_for_every_job(monkeypatch) -> None:
    async def handler(job):
        return make_score(job.id)

    seen = []
    service = _service(monkeypatch, RecordingProvider(), handler)
    await service.score_many(
        [make_job(f"j{i}") for i in range(3)], on_result=lambda j, r: seen.append(j.id)
    )
    assert sorted(seen) == ["j0", "j1", "j2"]


def test_the_gateway_provider_gets_a_tighter_concurrency() -> None:
    """Free-tier backends 429 much sooner than the paid ones."""
    config = Config()
    config.llm.provider = "freellmapi"
    assert concurrency_for(config) == 2
    config.llm.provider = "openai"
    assert concurrency_for(config) == 5


def test_scoring_an_empty_batch_is_free(monkeypatch) -> None:
    async def handler(job):  # pragma: no cover - must never be called
        raise AssertionError("no jobs to score")

    service = _service(monkeypatch, RecordingProvider(), handler)
    assert service.score_batch([]) == []
