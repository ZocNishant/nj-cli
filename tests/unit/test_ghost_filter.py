"""Unit tests for ghost job detection filter."""
from __future__ import annotations

from datetime import datetime, UTC, timedelta

import pytest

from nj.models.job import Job, VisaLabel, JobStatus
from nj.scoring.ghost_filter import GhostJobFilter, GhostJobResult, GhostSignal


_GOOD_DESC = (
    "We are looking for a machine learning engineer with 2+ years of experience "
    "working with PyTorch, Python, and distributed training. You will design and "
    "deploy production ML systems. H1B sponsorship available. Must have strong "
    "fundamentals in deep learning, model optimization, and MLOps practices."
)


def make_job(
    description: str = _GOOD_DESC,
    title: str = "ML Engineer",
    company: str = "Acme AI",
    scraped_days_ago: int = 1,
) -> Job:
    scraped = datetime.now(UTC) - timedelta(days=scraped_days_ago)
    return Job(
        id="test-id",
        title=title,
        company=company,
        url="https://example.com/job",
        description=description,
        location="Remote",
        source="remoteok",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=scraped,
        status=JobStatus.NEW,
        description_hash="abc",
    )


def test_clean_job_passes():
    f = GhostJobFilter()
    job = make_job()
    result = f.check(job)
    assert result.is_ghost is False


def test_stale_job_flagged():
    f = GhostJobFilter(max_age_days=30)
    job = make_job(scraped_days_ago=60)
    result = f.check(job)
    assert GhostSignal.STALE in result.signals


def test_stale_job_recent_passes():
    f = GhostJobFilter(max_age_days=30)
    job = make_job(scraped_days_ago=5)
    result = f.check(job)
    assert GhostSignal.STALE not in result.signals


def test_spam_pattern_flagged():
    f = GhostJobFilter()
    job = make_job(
        description=(
            "URGENT HIRING! Walk-in interview tomorrow. "
            "Make $500 per day working from home. No experience required."
        )
    )
    result = f.check(job)
    assert GhostSignal.SPAM_PATTERN in result.signals
    assert result.is_ghost is True


def test_vague_short_description():
    f = GhostJobFilter(min_description_length=200)
    job = make_job(description="We need a developer.")
    result = f.check(job)
    assert GhostSignal.VAGUE_DESCRIPTION in result.signals


def test_no_company_flagged():
    f = GhostJobFilter()
    job = make_job(company="Confidential")
    result = f.check(job)
    assert GhostSignal.NO_COMPANY_INFO in result.signals


def test_unknown_company_flagged():
    f = GhostJobFilter()
    job = make_job(company="Unknown")
    result = f.check(job)
    assert GhostSignal.NO_COMPANY_INFO in result.signals


def test_unrealistic_years_ml_role():
    f = GhostJobFilter()
    job = make_job(
        title="ML Engineer",
        description=(
            "Machine learning engineer needed. "
            "15 years of experience required. "
            "Must know PyTorch and TensorFlow deeply."
        ),
    )
    result = f.check(job)
    assert GhostSignal.UNREALISTIC_REQUIREMENTS in result.signals


def test_reasonable_years_passes():
    f = GhostJobFilter()
    job = make_job(
        title="ML Engineer",
        description=(
            "Machine learning engineer needed. "
            "3 years of experience required. "
            "Must know PyTorch and TensorFlow. "
            "H1B sponsorship available for right candidate."
        ),
    )
    result = f.check(job)
    assert GhostSignal.UNREALISTIC_REQUIREMENTS not in result.signals


def test_repost_detection():
    f = GhostJobFilter()
    desc = "A" * 300
    job1 = make_job(description=desc)
    job1.id = "j1"
    job2 = make_job(description=desc)
    job2.id = "j2"
    f.check(job1)
    result2 = f.check(job2)
    assert GhostSignal.MASS_REPOST in result2.signals


def test_filter_jobs_splits_correctly():
    f = GhostJobFilter(max_age_days=10)
    clean_job = make_job(scraped_days_ago=1)
    clean_job.id = "clean"
    ghost_job = make_job(scraped_days_ago=60, company="Unknown")
    ghost_job.id = "ghost"
    clean, ghosts = f.filter_jobs([clean_job, ghost_job])
    assert clean_job in clean
    assert any(j.id == "ghost" for j, _ in ghosts)


def test_filter_disabled_passes_all():
    f = GhostJobFilter(enabled=False)
    job = make_job(
        description="URGENT! Make $500/day!",
        company="Unknown",
        scraped_days_ago=100,
    )
    result = f.check(job)
    assert result.is_ghost is False


def test_confidence_increases_with_signals():
    f = GhostJobFilter(max_age_days=10)
    job = make_job(
        description="We need help.",
        company="Unknown",
        scraped_days_ago=60,
    )
    result = f.check(job)
    assert result.confidence > 0.5
    assert len(result.signals) >= 2


def test_reason_string_not_empty_when_ghost():
    f = GhostJobFilter()
    job = make_job(
        description="URGENT! Walk-in interview. Make $500 per day. No experience needed.",
    )
    result = f.check(job)
    if result.is_ghost:
        assert result.reason != ""
