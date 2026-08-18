"""Scoring a batch of jobs, concurrently, with the same rules everywhere.

`nj search` scored five jobs at a time behind a semaphore, with three attempts
and exponential backoff on 429. `nj run` scored them one at a time, in a `for`
loop, each job spinning up its own event loop via `asyncio.run` — same work,
several times slower, and with no rate-limit handling at all. There was no
reason for the difference; one of them simply got the improvement.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from nj.models.config import Config
from nj.models.job import Job
from nj.models.score import ScoreResult
from nj.providers.base import BaseLLMProvider
from nj.utils.logger import get_logger

logger = get_logger(__name__)

# Providers differ in how much parallelism they tolerate before returning 429.
# The gateway path fronts free-tier backends with much tighter limits.
_CONCURRENCY = {"freellmapi": 2, "groq": 2}
_DEFAULT_CONCURRENCY = 5

MAX_ATTEMPTS = 3


def concurrency_for(config: Config) -> int:
    return _CONCURRENCY.get(config.llm.provider.lower(), _DEFAULT_CONCURRENCY)


def _is_rate_limit(error: Exception) -> bool:
    text = str(error).lower()
    return "429" in text or "rate limit" in text or "rate_limit" in text


class ScoringService:
    """Scores jobs against the CV. Owns concurrency, retries and backoff."""

    def __init__(
        self,
        config: Config,
        provider: BaseLLMProvider,
        cv_base: dict,
        score_repo=None,
        concurrency: int | None = None,
    ):
        self.config = config
        self.provider = provider
        self.cv_base = cv_base
        self.score_repo = score_repo
        self.concurrency = concurrency or concurrency_for(config)

    async def score_one(self, job: Job) -> ScoreResult | None:
        """One job, retried on rate limits. None if it could not be scored.

        None rather than a raise: a single unscoreable posting must not end a
        batch, and `score_job` already degrades a parse failure to a zero
        result rather than throwing.
        """
        from nj.scoring.scorer import score_job

        for attempt in range(MAX_ATTEMPTS):
            try:
                return await score_job(
                    job=job,
                    cv_base=self.cv_base,
                    config=self.config,
                    provider=self.provider,
                    repo=self.score_repo,
                )
            except Exception as e:
                if _is_rate_limit(e) and attempt < MAX_ATTEMPTS - 1:
                    wait = 2**attempt * 5
                    logger.warning("score_rate_limited", job_id=job.id, wait=wait)
                    await asyncio.sleep(wait)
                    continue
                logger.warning("score_failed", job_id=job.id, error=str(e))
                return None
        return None

    async def score_many(
        self,
        jobs: list[Job],
        on_result: Callable[[Job, ScoreResult | None], None] | None = None,
    ) -> list[tuple[Job, ScoreResult]]:
        """Score a batch concurrently, preserving input order in the output.

        `on_result` fires as each job settles, which is how a caller drives a
        progress bar without the service knowing what a terminal is.
        """
        if not jobs:
            return []

        semaphore = asyncio.Semaphore(self.concurrency)

        async def run(job: Job) -> tuple[Job, ScoreResult | None]:
            async with semaphore:
                result = await self.score_one(job)
                if on_result is not None:
                    on_result(job, result)
                return job, result

        settled = await asyncio.gather(*[run(j) for j in jobs])
        return [(job, result) for job, result in settled if result is not None]

    def score_batch(
        self,
        jobs: list[Job],
        on_result: Callable[[Job, ScoreResult | None], None] | None = None,
    ) -> list[tuple[Job, ScoreResult]]:
        """Blocking entry point for the CLI. One event loop for the whole batch."""
        return asyncio.run(self.score_many(jobs, on_result=on_result))
