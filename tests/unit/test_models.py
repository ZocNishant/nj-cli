from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from nj.models.application import (
    ACTIVE_APPLICATION_STATUSES,
    ApplicationRecord,
    ApplicationStatus,
)
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


def test_generated_is_an_active_application_status():
    assert ApplicationStatus.GENERATED in ACTIVE_APPLICATION_STATUSES
    assert ApplicationStatus.SUBMITTED in ACTIVE_APPLICATION_STATUSES


def test_pipeline_never_writes_submitted():
    """SUBMITTED means a human sent it. Nothing automated may claim that.

    nj has no submit path — nj.applying.linkedin_easy raises by design — so a
    pipeline that writes SUBMITTED is asserting an application that does not
    exist, and `nj status` would report it as sent. The pipeline writes
    GENERATED; only `nj status --update-status submitted` promotes a row.
    """
    src = Path("nj/cli/cmd_run.py").read_text(encoding="utf-8")
    assert "ApplicationStatus.SUBMITTED" not in src
    assert "ApplicationStatus.GENERATED" in src


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
