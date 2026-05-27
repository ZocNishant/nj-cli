from __future__ import annotations

import pytest
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine

import nj.db.engine as engine_module
from nj.db.models import Base as ModelBase
from nj.db.repos.application_repo import ApplicationRepo
from nj.db.repos.score_repo import ScoreRepo
from nj.models.application import ApplicationRecord, ApplicationStatus, OutcomeType
from nj.models.score import ScoreResult, SubScore
from nj.analytics.outcomes import OutcomeReport, analyze_outcomes


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_score(job_id: str, total: int) -> ScoreResult:
    return ScoreResult(
        job_id=job_id,
        total_score=total,
        confidence=0.8,
        sub_scores=[],
        matched_skills=[],
        missing_skills=[],
        recommended_emphasis=[],
        visa_compatible=True,
        visa_notes="",
        overall_rationale="",
        scored_at=_now(),
        provider="test",
        prompt_version="v1",
    )


def _make_app(job_id: str, outcome: OutcomeType | None = None) -> ApplicationRecord:
    rec = ApplicationRecord.create(job_id=job_id, score=70)
    rec.status = ApplicationStatus.SUBMITTED
    rec.outcome = outcome
    rec.outcome_recorded_at = _now() if outcome else None
    return rec


@pytest.fixture()
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "outcomes_test.db")
    monkeypatch.setattr(engine_module, "_engine", None)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    ModelBase.metadata.create_all(engine)
    monkeypatch.setattr(engine_module, "_engine", engine)
    return path


# --- analyze_outcomes unit tests ---

class TestAnalyzeOutcomesEmpty:
    def test_empty_applications(self):
        report = analyze_outcomes([], {})
        assert report.total_with_outcomes == 0
        assert report.interview_rate_by_score_band == {}
        assert report.optimal_threshold is None
        assert report.score_outcome_pairs == []

    def test_no_outcomes_on_applications(self):
        apps = [_make_app("j1"), _make_app("j2")]
        report = analyze_outcomes(apps, {})
        assert report.total_with_outcomes == 0

    def test_outcomes_but_no_scores(self):
        apps = [_make_app("j1", OutcomeType.INTERVIEW)]
        report = analyze_outcomes(apps, {})
        assert report.total_with_outcomes == 1
        assert report.score_outcome_pairs == []
        assert "Scores not found" in report.recommendation


class TestAnalyzeOutcomesRates:
    def test_interview_rate_calculation(self):
        apps = [
            _make_app("j1", OutcomeType.INTERVIEW),
            _make_app("j2", OutcomeType.REJECTION),
            _make_app("j3", OutcomeType.REJECTION),
            _make_app("j4", OutcomeType.REJECTION),
        ]
        scores = {
            "j1": _make_score("j1", 75),
            "j2": _make_score("j2", 72),
            "j3": _make_score("j3", 71),
            "j4": _make_score("j4", 78),
        }
        report = analyze_outcomes(apps, scores)
        assert report.total_with_outcomes == 4
        assert len(report.score_outcome_pairs) == 4
        band_rate = report.interview_rate_by_score_band.get("70-79")
        assert band_rate == 25.0

    def test_offer_counts_as_interview(self):
        apps = [
            _make_app("j1", OutcomeType.OFFER),
            _make_app("j2", OutcomeType.REJECTION),
        ]
        scores = {
            "j1": _make_score("j1", 85),
            "j2": _make_score("j2", 82),
        }
        report = analyze_outcomes(apps, scores)
        band_rate = report.interview_rate_by_score_band.get("80-89")
        assert band_rate == 50.0

    def test_avg_scores(self):
        apps = [
            _make_app("j1", OutcomeType.INTERVIEW),
            _make_app("j2", OutcomeType.REJECTION),
        ]
        scores = {
            "j1": _make_score("j1", 80),
            "j2": _make_score("j2", 60),
        }
        report = analyze_outcomes(apps, scores)
        assert report.avg_score_interviews == 80.0
        assert report.avg_score_rejections == 60.0

    def test_optimal_threshold_found(self):
        apps = [
            _make_app("j1", OutcomeType.INTERVIEW),
            _make_app("j2", OutcomeType.INTERVIEW),
            _make_app("j3", OutcomeType.REJECTION),
        ]
        scores = {
            "j1": _make_score("j1", 82),
            "j2": _make_score("j2", 85),
            "j3": _make_score("j3", 81),
        }
        report = analyze_outcomes(apps, scores)
        assert report.optimal_threshold == 80
        assert "80" in report.recommendation

    def test_few_data_points_recommendation(self):
        apps = [_make_app("j1", OutcomeType.REJECTION)]
        scores = {"j1": _make_score("j1", 65)}
        report = analyze_outcomes(apps, scores)
        assert "data points" in report.recommendation.lower()
        assert "10+" in report.recommendation


class TestOutcomeTypes:
    def test_outcome_type_enum_values(self):
        assert OutcomeType.INTERVIEW.value == "interview"
        assert OutcomeType.REJECTION.value == "rejection"
        assert OutcomeType.OFFER.value == "offer"
        assert OutcomeType.NO_RESPONSE.value == "no_response"
        assert OutcomeType.UNKNOWN.value == "unknown"


class TestRecordOutcomeDB:
    def test_record_outcome_updates_applications(self, db_path):
        repo = ApplicationRepo(db_path)
        app = _make_app("job-abc")
        repo.save_application(app)

        count = repo.record_outcome("job-abc", OutcomeType.INTERVIEW)
        assert count == 1

        with_outcomes = repo.get_applications_with_outcomes()
        assert len(with_outcomes) == 1
        assert with_outcomes[0].outcome == OutcomeType.INTERVIEW
        assert with_outcomes[0].outcome_recorded_at is not None

    def test_get_applications_with_outcomes_empty(self, db_path):
        repo = ApplicationRepo(db_path)
        app = _make_app("job-xyz")
        repo.save_application(app)

        result = repo.get_applications_with_outcomes()
        assert result == []
