from __future__ import annotations

from nj.db.repos.job_repo import JobRepo
from nj.models.job import Job
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class JobDeduplicator:
    def __init__(self, repo: JobRepo):
        self.repo = repo

    def filter_new(self, jobs: list[Job]) -> list[Job]:
        new_jobs = []
        for job in jobs:
            if self.repo.job_exists(job.id):
                pass
            else:
                new_jobs.append(job)
        logger.info(
            "dedup_complete",
            total=len(jobs),
            new=len(new_jobs),
            duplicates=len(jobs) - len(new_jobs),
        )
        return new_jobs
