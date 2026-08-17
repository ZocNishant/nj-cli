from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine

import nj.db.engine as engine_module
from nj.db.models import Base as ModelBase
from nj.models.score import ScoreResult


def make_score(job_id: str = "test") -> ScoreResult:
    return ScoreResult(
        job_id=job_id,
        total_score=75,
        confidence=0.8,
        sub_scores=[],
        matched_skills=["PyTorch"],
        missing_skills=[],
        scored_at=datetime.now(UTC),
        provider="claude",
        prompt_version="scoring_v1",
        raw_response=None,
    )


def test_score_result_has_raw_response_field():
    score = make_score()
    assert hasattr(score, "raw_response")
    assert score.raw_response is None


def test_score_result_raw_response_stores_string():
    score = make_score()
    score.raw_response = '{"score": 75}'
    assert score.raw_response == '{"score": 75}'


def test_score_result_raw_response_optional():
    score = ScoreResult(
        job_id="test",
        total_score=75,
        confidence=0.8,
        scored_at=datetime.now(UTC),
        provider="claude",
        prompt_version="scoring_v1",
    )
    assert score.raw_response is None


def test_parse_failure_rate_zero_when_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(engine_module, "_engine", None)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    ModelBase.metadata.create_all(engine)
    monkeypatch.setattr(engine_module, "_engine", engine)

    from nj.db.repos.score_repo import ScoreRepo

    repo = ScoreRepo(db_path)
    stats = repo.get_parse_failure_rate()
    assert stats["total"] == 0
    assert stats["failures"] == 0
    assert stats["rate_pct"] == 0.0


def test_fixture_files_exist():
    fixtures = Path("tests/fixtures/scoring_regression")
    assert fixtures.exists()
    files = list(fixtures.glob("fixture_*.json"))
    assert len(files) >= 3


def test_fixture_structure_valid():
    fixtures = Path("tests/fixtures/scoring_regression")
    for f in fixtures.glob("fixture_*.json"):
        data = json.loads(f.read_text())
        assert "description" in data
        assert "job" in data
        assert "title" in data["job"]
