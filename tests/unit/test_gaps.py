from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from nj.analytics.skill_gaps import SkillGapReport, analyze_skill_gaps
from nj.models.score import ScoreResult


def make_score(
    job_id: str,
    total: int,
    matched: list[str],
    missing: list[str],
) -> ScoreResult:
    return ScoreResult(
        job_id=job_id,
        total_score=total,
        confidence=0.8,
        sub_scores=[],
        matched_skills=matched,
        missing_skills=missing,
        recommended_emphasis=[],
        visa_compatible=True,
        visa_notes="",
        overall_rationale="",
        scored_at=datetime.now(UTC),
        provider="claude",
        prompt_version="scoring_v1",
    )


def make_sample_scores() -> list[ScoreResult]:
    return [
        make_score("j1", 72, ["PyTorch", "OpenCV"], ["MLflow", "Kubernetes", "AWS"]),
        make_score("j2", 65, ["PyTorch", "Docker"], ["MLflow", "Kubernetes", "FastAPI"]),
        make_score("j3", 80, ["PyTorch", "FastAPI"], ["MLflow", "AWS", "Ray"]),
        make_score("j4", 58, ["TensorFlow"], ["PyTorch", "MLflow", "Kubernetes"]),
        make_score("j5", 70, ["PyTorch", "OpenCV"], ["MLflow", "W&B", "Kubernetes"]),
    ]


def test_analyze_returns_report() -> None:
    report = analyze_skill_gaps(make_sample_scores())
    assert isinstance(report, SkillGapReport)


def test_analyze_empty_returns_empty_report() -> None:
    report = analyze_skill_gaps([])
    assert report.total_jobs_analyzed == 0
    assert report.gaps == []
    assert report.avg_total_score == 0.0


def test_mlflow_is_top_gap() -> None:
    report = analyze_skill_gaps(make_sample_scores())
    top_skills = [g["skill"] for g in report.gaps[:3]]
    assert "mlflow" in top_skills


def test_kubernetes_appears_in_gaps() -> None:
    report = analyze_skill_gaps(make_sample_scores())
    skills = [g["skill"] for g in report.gaps]
    assert "kubernetes" in skills


def test_frequency_pct_calculation() -> None:
    report = analyze_skill_gaps(make_sample_scores())
    mlflow_gap = next((g for g in report.gaps if g["skill"] == "mlflow"), None)
    assert mlflow_gap is not None
    assert mlflow_gap["frequency_pct"] == 100
    assert mlflow_gap["job_count"] == 5


def test_avg_score_correct() -> None:
    report = analyze_skill_gaps(make_sample_scores())
    expected = (72 + 65 + 80 + 58 + 70) / 5
    assert abs(report.avg_total_score - expected) < 0.1


def test_total_jobs_analyzed() -> None:
    report = analyze_skill_gaps(make_sample_scores())
    assert report.total_jobs_analyzed == 5


def test_matched_skills_in_frequency() -> None:
    report = analyze_skill_gaps(make_sample_scores())
    matched_skills = [m["skill"] for m in report.matched_skill_frequency]
    assert "pytorch" in matched_skills


def test_pytorch_high_frequency_in_matched() -> None:
    report = analyze_skill_gaps(make_sample_scores())
    pytorch = next((m for m in report.matched_skill_frequency if m["skill"] == "pytorch"), None)
    assert pytorch is not None
    assert pytorch["frequency_pct"] >= 60


def test_profile_coverage_between_0_and_100() -> None:
    report = analyze_skill_gaps(make_sample_scores())
    assert 0.0 <= report.profile_coverage <= 100.0


def test_gaps_sorted_by_impact() -> None:
    report = analyze_skill_gaps(make_sample_scores())
    impacts = [g["impact_score"] for g in report.gaps]
    assert impacts == sorted(impacts, reverse=True)


def test_low_frequency_skills_excluded() -> None:
    scores = [make_score("j1", 70, ["PyTorch"], ["RareSkillXYZ"])]
    report = analyze_skill_gaps(scores, top_n=10)
    assert isinstance(report, SkillGapReport)


def test_run_gaps_no_jobs(tmp_path, monkeypatch) -> None:
    from nj.cli.cmd_gaps import run_gaps
    from nj.models.config import Config

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with (
        patch("nj.cli.cmd_gaps.console", c),
        patch("nj.db.repos.job_repo.JobRepo") as mock_repo_cls,
    ):
        mock_repo_cls.return_value.get_jobs.return_value = []
        run_gaps(Config(), db_path=str(tmp_path / "nj.db"))
    assert "No jobs found" in buf.getvalue()
