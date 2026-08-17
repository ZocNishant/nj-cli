from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from rich.console import Console

from nj.cli.cmd_explain import (
    _display_full_explanation,
    _show_top_jobs,
)
from nj.models.config import Config
from nj.models.job import Job, JobStatus, VisaLabel
from nj.models.score import ScoreCategory, ScoreResult, SubScore


def make_job(score: int = 75) -> Job:
    return Job(
        id="abc123def456",
        title="ML Engineer",
        company="Acme AI",
        url="https://example.com/job",
        description="PyTorch role. H1B sponsorship.",
        location="Remote USA",
        source="remoteok",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.SCORED,
        description_hash="abc",
    )


def make_score(total: int = 75) -> ScoreResult:
    return ScoreResult(
        job_id="abc123def456",
        total_score=total,
        confidence=0.87,
        sub_scores=[
            SubScore(
                category=ScoreCategory.SKILLS_MATCH,
                score=88,
                weight=0.30,
                rationale="Strong PyTorch match",
                evidence=["PyTorch expertise required"],
            ),
            SubScore(
                category=ScoreCategory.EXPERIENCE_RELEVANCE,
                score=62,
                weight=0.25,
                rationale="GastroVision relevant",
                evidence=["medical imaging"],
            ),
            SubScore(
                category=ScoreCategory.ROLE_ALIGNMENT,
                score=80,
                weight=0.20,
                rationale="Good alignment",
                evidence=["ML Engineer"],
            ),
            SubScore(
                category=ScoreCategory.SPONSORSHIP_COMPAT,
                score=95,
                weight=0.15,
                rationale="H1B offered",
                evidence=["H1B sponsorship available"],
            ),
            SubScore(
                category=ScoreCategory.LOCATION_FIT,
                score=90,
                weight=0.05,
                rationale="Remote USA",
                evidence=["Remote"],
            ),
            SubScore(
                category=ScoreCategory.RESUME_STRENGTH,
                score=74,
                weight=0.05,
                rationale="Strong projects",
                evidence=[],
            ),
        ],
        matched_skills=["PyTorch", "OpenCV", "EfficientNet"],
        missing_skills=["Kubernetes", "MLflow"],
        recommended_emphasis=["GastroVision", "medical imaging"],
        visa_compatible=True,
        visa_notes="H1B sponsorship explicitly offered.",
        overall_rationale="Strong CV match. GastroVision directly relevant.",
        scored_at=datetime.now(UTC),
        provider="claude",
        prompt_version="scoring_v1",
    )


def test_display_full_explanation_renders():
    job = make_job()
    score = make_score()
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_explain.console", c):
        _display_full_explanation(job, score)
    output = buf.getvalue()
    assert "ML Engineer" in output
    assert "Acme AI" in output
    assert "75" in output
    assert "PyTorch" in output


def test_display_shows_all_sub_scores():
    job = make_job()
    score = make_score()
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_explain.console", c):
        _display_full_explanation(job, score)
    output = buf.getvalue()
    assert "Skills Match" in output or "skills" in output.lower()
    assert "88" in output
    assert "95" in output


def test_display_shows_matched_and_missing():
    job = make_job()
    score = make_score()
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_explain.console", c):
        _display_full_explanation(job, score)
    output = buf.getvalue()
    assert "PyTorch" in output
    assert "Kubernetes" in output


def test_display_shows_recommendation():
    job = make_job()
    score = make_score(75)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_explain.console", c):
        _display_full_explanation(job, score)
    output = buf.getvalue()
    assert "Strong" in output or "approve" in output.lower()


def test_display_low_score_shows_skip_recommendation():
    job = make_job()
    score = make_score(45)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_explain.console", c):
        _display_full_explanation(job, score)
    output = buf.getvalue()
    assert "threshold" in output.lower() or "skip" in output.lower() or "Below" in output


def test_display_shows_visa_info():
    job = make_job()
    score = make_score()
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_explain.console", c):
        _display_full_explanation(job, score)
    output = buf.getvalue()
    assert "H1B" in output or "visa" in output.lower()


def test_show_top_jobs_no_jobs():
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    mock_job_repo = MagicMock()
    mock_job_repo.get_jobs.return_value = []
    mock_score_repo = MagicMock()
    with patch("nj.cli.cmd_explain.console", c):
        _show_top_jobs(mock_job_repo, mock_score_repo, 5)
    assert "No jobs found" in buf.getvalue()


def test_show_top_jobs_no_scores():
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    mock_job_repo = MagicMock()
    mock_job_repo.get_jobs.return_value = [make_job()]
    mock_score_repo = MagicMock()
    mock_score_repo.get_score.return_value = None
    with patch("nj.cli.cmd_explain.console", c):
        _show_top_jobs(mock_job_repo, mock_score_repo, 5)
    assert "No scored jobs" in buf.getvalue()


def test_show_top_jobs_renders_table():
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    mock_job_repo = MagicMock()
    mock_job_repo.get_jobs.return_value = [make_job()]
    mock_score_repo = MagicMock()
    mock_score_repo.get_score.return_value = make_score()
    with patch("nj.cli.cmd_explain.console", c):
        _show_top_jobs(mock_job_repo, mock_score_repo, 5)
    output = buf.getvalue()
    assert "Acme AI" in output
    assert "75" in output


def test_run_explain_no_job_id_shows_top(tmp_path, monkeypatch):
    from nj.cli.cmd_explain import run_explain

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    mock_job_repo = MagicMock()
    mock_job_repo.get_jobs.return_value = []
    with (
        patch("nj.cli.cmd_explain.console", c),
        patch("nj.cli.cmd_explain.JobRepo", return_value=mock_job_repo),
        patch("nj.cli.cmd_explain.ScoreRepo"),
    ):
        run_explain(Config(), db_path=str(tmp_path / "nj.db"))
    assert "No jobs found" in buf.getvalue()


def test_run_explain_partial_job_id_match(tmp_path, monkeypatch):
    from nj.cli.cmd_explain import run_explain

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    job = make_job()
    mock_job_repo = MagicMock()
    mock_job_repo.get_jobs.return_value = [job]
    mock_score_repo = MagicMock()
    mock_score_repo.get_score.return_value = make_score()
    with (
        patch("nj.cli.cmd_explain.console", c),
        patch("nj.cli.cmd_explain.JobRepo", return_value=mock_job_repo),
        patch("nj.cli.cmd_explain.ScoreRepo", return_value=mock_score_repo),
    ):
        run_explain(
            Config(),
            job_id="abc123",
            db_path=str(tmp_path / "nj.db"),
        )
    output = buf.getvalue()
    assert "ML Engineer" in output
