from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nj.db.engine import get_session
from nj.db.models import JobORM
from nj.models.job import Job, JobStatus, VisaLabel


class JobRepo:
    def __init__(self, db_path: str = "data/nj.db"):
        self.db_path = db_path

    def save_job(self, job: Job) -> None:
        with get_session(self.db_path) as session:
            existing = session.get(JobORM, job.id)
            if existing:
                existing.status = job.status.value
                existing.visa_label = job.visa_label.value
            else:
                session.add(
                    JobORM(
                        id=job.id,
                        title=job.title,
                        company=job.company,
                        url=job.url,
                        description=job.description,
                        location=job.location,
                        salary_raw=job.salary_raw,
                        source=job.source,
                        visa_label=job.visa_label.value,
                        scraped_at=job.scraped_at,
                        status=job.status.value,
                        description_hash=job.description_hash,
                    )
                )

    def job_exists(self, job_id: str) -> bool:
        with get_session(self.db_path) as session:
            return session.get(JobORM, job_id) is not None

    def get_job(self, job_id: str) -> Job | None:
        """One job by id, or None. Accepts a unique id prefix.

        The prefix form exists because these ids are 64-character hashes and
        every path that shows one to a human truncates it.
        """
        with get_session(self.db_path) as session:
            orm = session.get(JobORM, job_id)
            if orm is not None:
                return self._to_model(orm)

            matches = session.query(JobORM).filter(JobORM.id.startswith(job_id)).limit(2).all()
            if len(matches) == 1:
                return self._to_model(matches[0])
            return None

    def get_jobs(self, status: JobStatus | None = None) -> list[Job]:
        with get_session(self.db_path) as session:
            q = session.query(JobORM)
            if status:
                q = q.filter(JobORM.status == status.value)
            return [self._to_model(j) for j in q.all()]

    def get_recent_jobs(self, days: int = 30) -> list[Job]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        with get_session(self.db_path) as session:
            rows = session.query(JobORM).filter(JobORM.scraped_at >= cutoff).all()
            return [self._to_model(j) for j in rows]

    def update_job_status(self, job_id: str, status: JobStatus) -> None:
        with get_session(self.db_path) as session:
            job = session.get(JobORM, job_id)
            if job:
                job.status = status.value

    def update_visa_labels(self, labels: dict[str, VisaLabel]) -> int:
        """Rewrite stored visa labels in one transaction. Returns rows changed.

        Bulk rather than per-job because the caller is re-deriving every label
        from the current classifier: a partial write would leave the table
        split between two classifier versions, which is worse than either one
        alone. Rows whose label already matches are skipped so the count
        reflects real changes.
        """
        if not labels:
            return 0
        changed = 0
        with get_session(self.db_path) as session:
            for job_id, label in labels.items():
                job = session.get(JobORM, job_id)
                if job is not None and job.visa_label != label.value:
                    job.visa_label = label.value
                    changed += 1
        return changed

    def _to_model(self, orm: JobORM) -> Job:
        return Job(
            id=orm.id,
            title=orm.title,
            company=orm.company,
            url=orm.url,
            description=orm.description,
            location=orm.location,
            salary_raw=orm.salary_raw,
            source=orm.source,
            visa_label=VisaLabel(orm.visa_label),
            scraped_at=orm.scraped_at,
            status=JobStatus(orm.status),
            description_hash=orm.description_hash,
        )
