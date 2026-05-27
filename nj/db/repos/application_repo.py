from __future__ import annotations

from datetime import UTC, date, datetime

from nj.db.engine import get_session
from nj.db.models import ApplicationRecordORM
from nj.models.application import ApplicationRecord, ApplicationStatus, OutcomeType


class ApplicationRepo:
    def __init__(self, db_path: str = "data/nj.db"):
        self.db_path = db_path

    def save_application(self, record: ApplicationRecord) -> None:
        with get_session(self.db_path) as session:
            session.add(
                ApplicationRecordORM(
                    id=record.id,
                    job_id=record.job_id,
                    applied_at=record.applied_at,
                    status=record.status.value,
                    cv_path=record.cv_path,
                    cover_letter_path=record.cover_letter_path,
                    score=record.score,
                    error_message=record.error_message,
                    retry_count=record.retry_count,
                    screenshot_path=record.screenshot_path,
                    outcome=record.outcome.value if record.outcome else None,
                    outcome_recorded_at=record.outcome_recorded_at,
                )
            )

    def get_applications(
        self, status: ApplicationStatus | None = None
    ) -> list[ApplicationRecord]:
        with get_session(self.db_path) as session:
            q = session.query(ApplicationRecordORM)
            if status:
                q = q.filter(ApplicationRecordORM.status == status.value)
            return [self._to_model(r) for r in q.all()]

    def get_applications_with_outcomes(self) -> list[ApplicationRecord]:
        with get_session(self.db_path) as session:
            q = session.query(ApplicationRecordORM).filter(
                ApplicationRecordORM.outcome.isnot(None)
            )
            return [self._to_model(r) for r in q.all()]

    def count_today(self) -> int:
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())
        with get_session(self.db_path) as session:
            return (
                session.query(ApplicationRecordORM)
                .filter(
                    ApplicationRecordORM.status == ApplicationStatus.SUBMITTED.value,
                    ApplicationRecordORM.applied_at >= start_of_day,
                )
                .count()
            )

    def update_status(self, app_id: str, status: ApplicationStatus, **kwargs) -> None:
        with get_session(self.db_path) as session:
            record = session.get(ApplicationRecordORM, app_id)
            if record:
                record.status = status.value
                for k, v in kwargs.items():
                    if hasattr(record, k):
                        setattr(record, k, v)

    def record_outcome(self, job_id: str, outcome: OutcomeType) -> int:
        with get_session(self.db_path) as session:
            records = (
                session.query(ApplicationRecordORM)
                .filter(ApplicationRecordORM.job_id == job_id)
                .all()
            )
            now = datetime.now(UTC).replace(tzinfo=None)
            for r in records:
                r.outcome = outcome.value
                r.outcome_recorded_at = now
            return len(records)

    def _to_model(self, orm: ApplicationRecordORM) -> ApplicationRecord:
        return ApplicationRecord(
            id=orm.id,
            job_id=orm.job_id,
            applied_at=orm.applied_at,
            status=ApplicationStatus(orm.status),
            cv_path=orm.cv_path,
            cover_letter_path=orm.cover_letter_path,
            score=orm.score,
            error_message=orm.error_message,
            retry_count=orm.retry_count,
            screenshot_path=orm.screenshot_path,
            outcome=OutcomeType(orm.outcome) if orm.outcome else None,
            outcome_recorded_at=orm.outcome_recorded_at,
        )
