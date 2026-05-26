from __future__ import annotations

import pytest
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import nj.db.engine as engine_module
from nj.db.models import Base as ModelBase
from nj.db.repos.job_repo import JobRepo
from nj.db.repos.score_repo import ScoreRepo
from nj.db.repos.application_repo import ApplicationRepo
from nj.db.repos.label_repo import LabelRepo
from nj.models.job import Job, JobStatus, VisaLabel
from nj.models.score import ScoreResult, ScoreCategory, SubScore
from nj.models.application import ApplicationRecord, ApplicationStatus
from nj.models.label import JobLabel, LabelValue


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "test.db")
    # Reset the singleton so each test gets a fresh engine pointed at tmp_path.
    monkeypatch.setattr(engine_module, "_engine", None)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    monkeypatch.setattr(engine_module, "_engine", engine)
    ModelBase.metadata.create_all(engine)
    return path


def _make_job(job_id: str | None = None) -> Job:
    jid = job_id or Job.generate_id("Acme", "ML Engineer", "https://acme.com/1")
    return Job(
        id=jid,
        title="ML Engineer",
        company="Acme",
        url="https://acme.com/1",
        description="Build models",
        location="Remote",
        source="indeed",
        scraped_at=_now(),
        description_hash=Job.generate_hash("Build models"),
    )


# --- JobRepo ---

def test_save_job_then_job_exists(db_path):
    repo = JobRepo(db_path)
    job = _make_job()
    repo.save_job(job)
    assert repo.job_exists(job.id) is True


def test_job_exists_false_for_unknown(db_path):
    repo = JobRepo(db_path)
    assert repo.job_exists("nonexistent-id") is False


def test_save_job_then_get_jobs(db_path):
    repo = JobRepo(db_path)
    job = _make_job()
    repo.save_job(job)
    jobs = repo.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == job.id
    assert jobs[0].title == "ML Engineer"


def test_update_job_status(db_path):
    repo = JobRepo(db_path)
    job = _make_job()
    repo.save_job(job)
    repo.update_job_status(job.id, JobStatus.SCORED)
    jobs = repo.get_jobs(status=JobStatus.SCORED)
    assert len(jobs) == 1
    assert jobs[0].status == JobStatus.SCORED


# --- ScoreRepo ---

def test_save_score_then_get_score(db_path):
    repo = ScoreRepo(db_path)
    result = ScoreResult(
        job_id="job-abc",
        total_score=75,
        confidence=0.9,
        sub_scores=[
            SubScore(
                category=ScoreCategory.SKILLS_MATCH,
                score=80,
                weight=0.5,
                rationale="good match",
            )
        ],
        matched_skills=["Python", "PyTorch"],
        missing_skills=["Scala"],
        recommended_emphasis=["CV experience"],
        visa_compatible=True,
        visa_notes="OPT ok",
        overall_rationale="Strong candidate",
        scored_at=_now(),
        provider="claude",
        prompt_version="v1",
    )
    repo.save_score(result)
    fetched = repo.get_score("job-abc")
    assert fetched is not None
    assert fetched.total_score == 75
    assert fetched.matched_skills == ["Python", "PyTorch"]
    assert fetched.sub_scores[0].score == 80


# --- ApplicationRepo ---

def test_save_application_then_get_applications(db_path):
    repo = ApplicationRepo(db_path)
    record = ApplicationRecord.create(job_id="job-xyz", score=80)
    repo.save_application(record)
    apps = repo.get_applications()
    assert len(apps) == 1
    assert apps[0].job_id == "job-xyz"
    assert apps[0].score == 80


def test_count_today_returns_zero_when_no_submitted(db_path):
    repo = ApplicationRepo(db_path)
    record = ApplicationRecord.create(job_id="job-xyz", score=80)
    repo.save_application(record)  # status is PENDING, not SUBMITTED
    assert repo.count_today() == 0


# --- LabelRepo ---

def test_save_label_then_get_labels(db_path):
    repo = LabelRepo(db_path)
    label = JobLabel(
        job_id="job-123",
        label=LabelValue.YES,
        user_rationale="Great fit",
        labeled_at=_now(),
        score_at_label_time=78,
    )
    repo.save_label(label)
    labels = repo.get_labels()
    assert len(labels) == 1
    assert labels[0].job_id == "job-123"
    assert labels[0].label == LabelValue.YES
    assert labels[0].score_at_label_time == 78
