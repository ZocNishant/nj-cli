from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nj.models.application import ApplicationRecord, ApplicationStatus
from nj.models.config import Config
from nj.models.job import Job
from nj.models.label import LabelValue
from nj.models.score import ScoreCategory, ScoreResult, SubScore


def _now() -> datetime:
    return datetime.now(UTC)


# --- Job ---


def test_generate_id_is_deterministic():
    a = Job.generate_id("Acme", "ML Engineer", "https://acme.com/jobs/1")
    b = Job.generate_id("Acme", "ML Engineer", "https://acme.com/jobs/1")
    assert a == b


def test_generate_id_differs_for_different_inputs():
    a = Job.generate_id("Acme", "ML Engineer", "https://acme.com/jobs/1")
    b = Job.generate_id("Acme", "Data Scientist", "https://acme.com/jobs/2")
    assert a != b


# --- ScoreResult ---


def test_compute_total_weighted_average():
    sub_scores = [
        SubScore(
            category=ScoreCategory.SKILLS_MATCH,
            score=80,
            weight=0.5,
            rationale="good",
        ),
        SubScore(
            category=ScoreCategory.ROLE_ALIGNMENT,
            score=60,
            weight=0.5,
            rationale="ok",
        ),
    ]
    assert ScoreResult.compute_total(sub_scores) == 70


def test_subscore_raises_if_score_above_100():
    with pytest.raises(ValueError):
        SubScore(
            category=ScoreCategory.SKILLS_MATCH,
            score=101,
            weight=0.5,
            rationale="bad",
        )


# --- ApplicationRecord ---


def test_application_record_create_sets_job_id():
    record = ApplicationRecord.create(job_id="abc123", score=75)
    assert record.job_id == "abc123"
    assert record.score == 75
    assert record.status == ApplicationStatus.PENDING
    assert record.id  # uuid was generated


# --- Config ---


def test_config_load_returns_defaults_when_no_file(tmp_path):
    cfg = Config.load(str(tmp_path / "nonexistent.yaml"))
    assert cfg.scoring.threshold == 62
    assert cfg.llm.provider == "claude"
    assert cfg.apply.enabled is False


# --- LabelValue ---


def test_label_value_enum_members():
    assert LabelValue.YES == "yes"
    assert LabelValue.NO == "no"
    assert LabelValue.MAYBE == "maybe"
