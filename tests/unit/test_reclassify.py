from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nj.cli.cmd_reclassify import reclassify_jobs
from nj.models.config import Config, VisaConfig
from nj.models.job import Job, JobStatus, VisaLabel


def make_job(job_id: str, description: str, stored: VisaLabel) -> Job:
    return Job(
        id=job_id,
        title="ML Engineer",
        company="Acme",
        url="https://example.com/j",
        description=description,
        location="Remote",
        salary_raw="",
        source="test",
        visa_label=stored,
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash=job_id,
    )


@pytest.fixture
def config() -> Config:
    cfg = Config()
    cfg.visa = VisaConfig(enabled=True)
    return cfg


def test_reclassify_corrects_the_optimization_false_positive(config: Config) -> None:
    """The bug this command exists to clean up.

    The old substring matcher read `opt` inside "optimization" as Optional
    Practical Training and stored CONFIRMED. Re-deriving must produce UNKNOWN
    and report the flip.
    """
    job = make_job("j1", "Strong optimization background required.", VisaLabel.CONFIRMED)
    (result,) = reclassify_jobs([job], config)
    assert result.old == VisaLabel.CONFIRMED
    assert result.new == VisaLabel.UNKNOWN
    assert result.flipped


def test_reclassify_catches_a_stored_confirmed_that_actually_refuses(config: Config) -> None:
    """CONFIRMED -> BLOCKED is the worst flip and must sort first."""
    job = make_job("j2", "We are unable to offer sponsorship for this role.", VisaLabel.CONFIRMED)
    (result,) = reclassify_jobs([job], config)
    assert result.new == VisaLabel.BLOCKED
    assert "sponsor" in result.evidence.lower()
    # Ranked above the merely-unsignalled case, so a reviewer reading the top of
    # the sample sees stated refusals before absent signals.
    unsignalled = reclassify_jobs(
        [make_job("j3", "Nothing relevant here.", VisaLabel.CONFIRMED)], config
    )[0]
    assert result.severity < unsignalled.severity


def test_reclassify_leaves_a_correct_label_alone(config: Config) -> None:
    job = make_job("j4", "We sponsor H-1B visas for qualified candidates.", VisaLabel.CONFIRMED)
    (result,) = reclassify_jobs([job], config)
    assert result.new == VisaLabel.CONFIRMED
    assert not result.flipped


def test_reclassify_reports_evidence_for_every_job(config: Config) -> None:
    """The evidence string is the reviewable part — it must never be empty."""
    jobs = [
        make_job("a", "Strong optimization background.", VisaLabel.CONFIRMED),
        make_job("b", "We do not sponsor employment visas.", VisaLabel.CONFIRMED),
        make_job("c", "", VisaLabel.UNKNOWN),
    ]
    for result in reclassify_jobs(jobs, config):
        assert result.evidence.strip()


def test_reclassify_survives_a_job_with_no_description(config: Config) -> None:
    job = make_job("j5", "", VisaLabel.CONFIRMED)
    job.description = None  # a row that predates the not-null expectation
    (result,) = reclassify_jobs([job], config)
    assert result.new == VisaLabel.UNKNOWN


def test_update_visa_labels_only_counts_real_changes(tmp_path) -> None:
    from nj.db.engine import init_db
    from nj.db.repos.job_repo import JobRepo

    db = str(tmp_path / "t.db")
    init_db(db)
    repo = JobRepo(db)
    repo.save_job(make_job("k1", "x", VisaLabel.CONFIRMED))
    repo.save_job(make_job("k2", "y", VisaLabel.UNKNOWN))

    # k1 changes, k2 is already correct.
    changed = repo.update_visa_labels(
        {"k1": VisaLabel.UNKNOWN, "k2": VisaLabel.UNKNOWN},
    )
    assert changed == 1
    assert {j.id: j.visa_label for j in repo.get_jobs()} == {
        "k1": VisaLabel.UNKNOWN,
        "k2": VisaLabel.UNKNOWN,
    }


def test_update_visa_labels_is_idempotent(tmp_path) -> None:
    """A second pass must report zero, so `nj reclassify` converges."""
    from nj.db.engine import init_db
    from nj.db.repos.job_repo import JobRepo

    db = str(tmp_path / "t2.db")
    init_db(db)
    repo = JobRepo(db)
    repo.save_job(make_job("k3", "x", VisaLabel.CONFIRMED))

    assert repo.update_visa_labels({"k3": VisaLabel.UNKNOWN}) == 1
    assert repo.update_visa_labels({"k3": VisaLabel.UNKNOWN}) == 0


def test_update_visa_labels_ignores_unknown_job_ids(tmp_path) -> None:
    from nj.db.engine import init_db
    from nj.db.repos.job_repo import JobRepo

    db = str(tmp_path / "t3.db")
    init_db(db)
    repo = JobRepo(db)
    assert repo.update_visa_labels({"does-not-exist": VisaLabel.BLOCKED}) == 0
