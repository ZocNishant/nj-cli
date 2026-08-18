"""Scrape, deduplicate, store, and drop the ghosts.

The first three stages of both pipelines, which were identical in intent and
divergent in detail. Returns a result object rather than printing, so the
caller owns presentation and the service can be tested without a terminal.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from nj.models.config import Config
from nj.models.job import Job
from nj.scrapers.base import BaseScraper
from nj.utils.logger import get_logger

logger = get_logger(__name__)

# A posting this old is either filled or was never real. Shared by both
# pipelines, which each hardcoded it separately.
GHOST_MAX_AGE_DAYS = 45


@dataclass
class IngestResult:
    """What one ingest produced, and enough detail to explain it to a human."""

    jobs: list[Job] = field(default_factory=list)
    per_source: dict[str, int] = field(default_factory=dict)
    scraped: int = 0
    duplicates: int = 0
    ghosts: list[tuple[Job, object]] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def sources_line(self) -> str:
        return " · ".join(f"{name}={count}" for name, count in self.per_source.items())


class IngestService:
    def __init__(self, config: Config, job_repo, scrapers: list[BaseScraper] | None = None):
        self.config = config
        self.job_repo = job_repo
        self._scrapers = scrapers

    @property
    def scrapers(self) -> list[BaseScraper]:
        if self._scrapers is None:
            from nj.pipeline.sources import build_scrapers

            self._scrapers = build_scrapers(self.config)
        return self._scrapers

    async def _scrape_one(self, scraper: BaseScraper) -> tuple[str, list[Job]]:
        """One source. Never raises — a dead board must not end the run."""
        try:
            jobs = await scraper.scrape(
                self.config.search.roles,
                self.config.search.primary_region,
            )
            logger.info("scraper_done", scraper=scraper.name(), count=len(jobs))
            return scraper.name(), list(jobs)
        except Exception as e:
            logger.warning("scraper_failed", scraper=scraper.name(), error=str(e))
            return scraper.name(), []

    async def scrape(self) -> dict[str, list[Job]]:
        results = await asyncio.gather(
            *[self._scrape_one(s) for s in self.scrapers], return_exceptions=True
        )
        output: dict[str, list[Job]] = {}
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("scraper_gather_failed", error=str(result))
                continue
            name, jobs = result
            output[name] = jobs
        return output

    def enrich(self, jobs: list[Job], cv_base: dict | None, db_path: str) -> dict[str, dict]:
        """Attach sponsorship, salary, semantic and USCIS signals, and store them.

        This ran in `nj search` and not in `nj run`, so a job that arrived
        through the batch pipeline never got a sponsorship probability, a
        salary band or a semantic score — and `nj explain` on that job had
        nothing to show. It is local model work, no API spend.

        Never raises: enrichment is additive, and a missing model must not
        cost the run the jobs it already has.
        """
        if not jobs:
            return {}
        try:
            from nj.db.repos.enrichment_repo import EnrichmentRepo
            from nj.intel.enrichment import JobEnrichment

            enrichments = JobEnrichment(db_path=db_path).enrich_batch(jobs, cv_base)
            repo = EnrichmentRepo(db_path=db_path)
            for job_id, enrichment in enrichments.items():
                repo.save_enrichment(job_id, enrichment)
            return enrichments
        except Exception as e:
            logger.warning("enrichment_failed", error=str(e), jobs=len(jobs))
            return {}

    def collect(self, save: bool = True) -> IngestResult:
        """Scrape every source, keep what is new and real, and store it.

        `save=False` is for a caller that wants the candidate list without
        writing — note that `nj search --dry-run` does still save, because a
        posting seen is worth keeping even when the scoring spend is skipped.
        """
        from nj.scoring.ghost_filter import GhostJobFilter
        from nj.utils.dedup import JobDeduplicator

        started = time.monotonic()
        per_source_jobs = asyncio.run(self.scrape())
        elapsed = round(time.monotonic() - started, 1)

        raw: list[Job] = []
        per_source: dict[str, int] = {}
        for name, jobs in per_source_jobs.items():
            per_source[name] = len(jobs)
            raw.extend(jobs)

        new_jobs = JobDeduplicator(self.job_repo).filter_new(raw)
        if save:
            for job in new_jobs:
                self.job_repo.save_job(job)

        kept, ghosts = GhostJobFilter(enabled=True, max_age_days=GHOST_MAX_AGE_DAYS).filter_jobs(
            new_jobs
        )

        return IngestResult(
            jobs=kept,
            per_source=per_source,
            scraped=len(raw),
            duplicates=len(raw) - len(new_jobs),
            ghosts=ghosts,
            elapsed_seconds=elapsed,
        )
