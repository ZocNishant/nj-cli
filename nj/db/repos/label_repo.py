from __future__ import annotations

from nj.db.engine import get_session
from nj.db.models import JobLabelORM, JobORM, ScoreResultORM
from nj.models.label import JobLabel, LabelValue


class LabelRepo:
    def __init__(self, db_path: str = "data/nj.db"):
        self.db_path = db_path

    def save_label(self, label: JobLabel) -> None:
        with get_session(self.db_path) as session:
            existing = session.get(JobLabelORM, label.job_id)
            if existing:
                existing.label = label.label.value
                existing.user_rationale = label.user_rationale
                existing.labeled_at = label.labeled_at
                existing.score_at_label_time = label.score_at_label_time
            else:
                session.add(
                    JobLabelORM(
                        job_id=label.job_id,
                        label=label.label.value,
                        user_rationale=label.user_rationale,
                        labeled_at=label.labeled_at,
                        score_at_label_time=label.score_at_label_time,
                    )
                )

    def get_unlabeled_scored_jobs(self, limit: int = 20) -> list[tuple]:
        from nj.models.job import Job, JobStatus, VisaLabel
        from nj.models.score import ScoreCategory, ScoreResult, SubScore

        with get_session(self.db_path) as session:
            labeled_ids = {row.job_id for row in session.query(JobLabelORM).all()}
            score_rows = session.query(ScoreResultORM).limit(limit * 3).all()
            valid_categories = {c.value for c in ScoreCategory}
            pairs = []
            for sr in score_rows:
                if sr.job_id in labeled_ids:
                    continue
                job_orm = session.get(JobORM, sr.job_id)
                if not job_orm:
                    continue
                job = Job(
                    id=job_orm.id,
                    title=job_orm.title,
                    company=job_orm.company,
                    url=job_orm.url,
                    description=job_orm.description,
                    location=job_orm.location or "",
                    source=job_orm.source,
                    visa_label=VisaLabel(job_orm.visa_label),
                    scraped_at=job_orm.scraped_at,
                    status=JobStatus(job_orm.status),
                    description_hash=job_orm.description_hash,
                )
                sub_scores_raw = sr.sub_scores or []
                sub_scores = [
                    SubScore(
                        category=ScoreCategory(s["category"]),
                        score=s["score"],
                        weight=s.get("weight", 0.0),
                        rationale=s.get("rationale", ""),
                    )
                    for s in sub_scores_raw
                    if s.get("category") in valid_categories
                ]
                result = ScoreResult(
                    job_id=sr.job_id,
                    total_score=sr.total_score,
                    confidence=sr.confidence,
                    sub_scores=sub_scores,
                    matched_skills=sr.matched_skills or [],
                    missing_skills=sr.missing_skills or [],
                    recommended_emphasis=sr.recommended_emphasis or [],
                    overall_rationale=sr.overall_rationale or "",
                    scored_at=sr.scored_at,
                )
                pairs.append((job, result))
                if len(pairs) >= limit:
                    break
            return pairs

    def get_labels(self) -> list[JobLabel]:
        with get_session(self.db_path) as session:
            rows = session.query(JobLabelORM).all()
            return [
                JobLabel(
                    job_id=r.job_id,
                    label=LabelValue(r.label),
                    user_rationale=r.user_rationale,
                    labeled_at=r.labeled_at,
                    score_at_label_time=r.score_at_label_time,
                )
                for r in rows
            ]
