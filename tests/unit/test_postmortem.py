"""Unit tests for application postmortem analysis."""
from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import patch
from io import StringIO

import pytest

from nj.models.application import ApplicationRecord, ApplicationStatus, OutcomeType
from nj.models.score import ScoreResult, SubScore, ScoreCategory
from nj.models.job import Job, VisaLabel, JobStatus
from nj.analytics.outcomes_analysis import (
    analyze_postmortem,
    PostmortemReport,
    _categorize_role,
    _detect_patterns,
)


def make_app(
    job_id: str,
    outcome: OutcomeType | None = None,
    score: int = 70,
) -> ApplicationRecord:
    return ApplicationRecord(
        id=f"app-{job_id}",
        job_id=job_id,
        applied_at=datetime.now(UTC),
        status=ApplicationStatus.SUBMITTED,
        score=score,
        outcome=outcome,
    )


def make_score(
    job_id: str,
    total: int = 70,
    exp_score: int = 60,
) -> ScoreResult:
    return ScoreResult(
        job_id=job_id,
        total_score=total,
        confidence=0.8,
        sub_scores=[
            SubScore(
                category=ScoreCategory.SKILLS_MATCH,
                score=80,
                weight=0.30,
                rationale="test",
                evidence=[],
            ),
            SubScore(
                category=ScoreCategory.EXPERIENCE_RELEVANCE,
                score=exp_score,
                weight=0.25,
                rationale="test",
                evidence=[],
            ),
        ],
        matched_skills=["PyTorch"],
        missing_skills=["Kubernetes", "MLflow"],
        scored_at=datetime.now(UTC),
        provider="claude",
        prompt_version="scoring_v1",
    )


def make_job(
    job_id: str,
    title: str = "ML Engineer",
    company: str = "Acme",
    visa_label: VisaLabel = VisaLabel.CONFIRMED,
) -> Job:
    return Job(
        id=job_id,
        title=title,
        company=company,
        url=f"https://example.com/{job_id}",
        description="ML role",
        location="Remote",
        source="remoteok",
        visa_label=visa_label,
        scraped_at=datetime.now(UTC),
        status=JobStatus.APPLIED,
        description_hash=job_id,
    )


def test_empty_applications():
    report = analyze_postmortem([], {}, {})
    assert report.total_applications == 0
    assert report.interview_rate == 0.0


def test_basic_rates():
    apps = [
        make_app("j1", OutcomeType.INTERVIEW),
        make_app("j2", OutcomeType.REJECTION),
        make_app("j3", OutcomeType.REJECTION),
        make_app("j4", OutcomeType.NO_RESPONSE),
    ]
    scores = {k: make_score(k, s) for k, s in [("j1", 80), ("j2", 60), ("j3", 55), ("j4", 65)]}
    jobs = {k: make_job(k) for k in ["j1", "j2", "j3", "j4"]}
    report = analyze_postmortem(apps, scores, jobs)
    assert report.total_applications == 4
    assert report.interview_rate == 25.0
    assert report.rejection_rate == 50.0


def test_avg_score_interviews_higher():
    apps = [
        make_app("j1", OutcomeType.INTERVIEW),
        make_app("j2", OutcomeType.REJECTION),
    ]
    scores = {"j1": make_score("j1", 85), "j2": make_score("j2", 55)}
    jobs = {k: make_job(k) for k in ["j1", "j2"]}
    report = analyze_postmortem(apps, scores, jobs)
    assert report.avg_score_interviews > report.avg_score_rejections


def test_score_distribution_populated():
    apps = [make_app(f"j{i}") for i in range(5)]
    scores = {f"j{i}": make_score(f"j{i}", 50 + i * 10) for i in range(5)}
    jobs = {k: make_job(k) for k in scores}
    report = analyze_postmortem(apps, scores, jobs)
    total_in_bands = sum(report.score_distribution.values())
    scored_count = sum(1 for a in apps if a.job_id in scores)
    assert total_in_bands == scored_count


def test_skill_gap_patterns_detected():
    apps = [make_app(f"j{i}", OutcomeType.REJECTION) for i in range(5)]
    scores = {f"j{i}": make_score(f"j{i}", 60) for i in range(5)}
    jobs = {k: make_job(k) for k in scores}
    report = analyze_postmortem(apps, scores, jobs)
    skill_names = [g["skill"] for g in report.skill_gap_patterns]
    assert "Kubernetes" in skill_names or "MLflow" in skill_names


def test_categorize_role():
    assert _categorize_role("Machine Learning Engineer") == "ML Engineer"
    assert _categorize_role("Computer Vision Engineer") == "CV Engineer"
    assert _categorize_role("Research Scientist") == "Research"
    assert _categorize_role("Data Scientist") == "Data Science"
    assert _categorize_role("Unknown Role XYZ") == "Other"


def test_recommendations_not_empty():
    apps = [make_app("j1", OutcomeType.REJECTION)]
    scores = {"j1": make_score("j1", 55)}
    jobs = {"j1": make_job("j1")}
    report = analyze_postmortem(apps, scores, jobs)
    assert len(report.recommendations) > 0


def test_visa_blocked_pattern():
    apps = [
        make_app("j1", OutcomeType.REJECTION),
        make_app("j2", OutcomeType.REJECTION),
    ]
    scores = {"j1": make_score("j1", 70), "j2": make_score("j2", 68)}
    jobs = {
        "j1": make_job("j1", visa_label=VisaLabel.BLOCKED),
        "j2": make_job("j2", visa_label=VisaLabel.BLOCKED),
    }
    report = analyze_postmortem(apps, scores, jobs)
    pattern_types = [p.pattern_type for p in report.patterns]
    assert "visa_blocked_applications" in pattern_types


def test_role_type_analysis_populated():
    apps = [
        make_app("j1", OutcomeType.INTERVIEW),
        make_app("j2", OutcomeType.REJECTION),
        make_app("j3", OutcomeType.REJECTION),
    ]
    scores = {k: make_score(k) for k in ["j1", "j2", "j3"]}
    jobs = {
        "j1": make_job("j1", "ML Engineer"),
        "j2": make_job("j2", "Computer Vision Engineer"),
        "j3": make_job("j3", "ML Engineer"),
    }
    report = analyze_postmortem(apps, scores, jobs)
    assert "ML Engineer" in report.role_type_analysis


def test_run_postmortem_no_applications(tmp_path, monkeypatch):
    from rich.console import Console
    from nj.cli.cmd_postmortem import run_postmortem
    from nj.models.config import Config

    monkeypatch.chdir(tmp_path)
    import nj.db.engine as eng
    eng._engine = None
    db_path = str(tmp_path / "test.db")
    from nj.db.engine import init_db
    init_db(db_path)

    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_postmortem.console", c):
        run_postmortem(Config(), db_path=db_path)
    assert "No applications" in buf.getvalue()
