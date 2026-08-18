from __future__ import annotations

import re

from nj.db.repos.job_repo import JobRepo
from nj.models.job import Job
from nj.utils.logger import get_logger

logger = get_logger(__name__)

_PUNCT = re.compile(r"[^a-z0-9]+")


def _norm(text: str) -> str:
    """Fold a company or title down to something two boards would agree on."""
    return _PUNCT.sub(" ", (text or "").lower()).strip()


def content_key(job: Job) -> str:
    """The identity of a *posting*, independent of where it was found.

    `Job.id` hashes the URL, so the same role syndicated to RemoteOK and
    WeWorkRemotely is two ids, two rows, two scoring calls, and two chances to
    tailor the same application twice. Aggregators make that the common case,
    not the edge case.

    Preferring `description_hash` matches verbatim reposts — the usual shape,
    since boards republish the employer's own text. Normalised company+title is
    the fallback for a board that reformats the body.
    """
    if job.description_hash:
        return f"h:{job.description_hash}"
    return f"n:{_norm(job.company)}|{_norm(job.title)}"


class JobDeduplicator:
    def __init__(self, repo: JobRepo):
        self.repo = repo

    def filter_new(self, jobs: list[Job]) -> list[Job]:
        """Jobs not already stored and not repeated within this batch.

        Two passes. The first asks the database once for the whole batch rather
        than once per job — `job_exists` opened a session per call, so a
        470-job scrape was 470 connection cycles to answer one question. The
        second collapses postings that are the same role reached by different
        URLs, which the id check structurally cannot see.
        """
        if not jobs:
            logger.info("dedup_complete", total=0, new=0, duplicates=0, cross_source=0)
            return []

        known_ids = self.repo.existing_ids([j.id for j in jobs])

        new_jobs: list[Job] = []
        seen_content: set[str] = set()
        cross_source = 0

        for job in jobs:
            if job.id in known_ids:
                continue
            key = content_key(job)
            if key in seen_content:
                cross_source += 1
                logger.debug(
                    "dedup_cross_source",
                    company=job.company,
                    title=job.title,
                    source=job.source,
                )
                continue
            seen_content.add(key)
            new_jobs.append(job)

        logger.info(
            "dedup_complete",
            total=len(jobs),
            new=len(new_jobs),
            duplicates=len(jobs) - len(new_jobs),
            cross_source=cross_source,
        )
        return new_jobs
