from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from nj.models.config import Config
from nj.models.job import Job, JobStatus, VisaLabel
from nj.models.quality import GateDecision
from nj.models.score import ScoreResult
from nj.scoring.quality_gate import check_application_quality


def make_job(description: str = "ML Engineer role. H1B sponsorship available.") -> Job:
    return Job(
        id="test-id",
        title="ML Engineer",
        company="Acme Corp",
        url="https://example.com",
        description=description,
        location="San Francisco",
        source="remoteok",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.TAILORED,
        description_hash="abc",
    )


def make_score(total: int = 75, confidence: float = 0.85) -> ScoreResult:
    return ScoreResult(
        job_id="test-id",
        total_score=total,
        confidence=confidence,
        sub_scores=[],
        matched_skills=["PyTorch", "OpenCV"],
        missing_skills=["Kubernetes"],
        recommended_emphasis=["GastroVision"],
        visa_compatible=True,
        visa_notes="H1B offered",
        overall_rationale="Good match.",
        scored_at=datetime.now(UTC),
        provider="claude",
        prompt_version="scoring_v1",
    )


def make_cv() -> dict:
    return {
        "personal": {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+1 555 0000",
            "linkedin": "linkedin.com/in/test",
        }
    }


def make_config(threshold: int = 62) -> Config:
    config = Config()
    config.scoring.threshold = threshold
    return config


def test_approved_on_good_application() -> None:
    result = check_application_quality(
        job=make_job(),
        tailored_cv=make_cv(),
        cover_letter="Strong engineering background with PyTorch.",
        score=make_score(75),
        config=make_config(),
    )
    assert result.decision == GateDecision.APPROVED
    assert result.is_approved is True


def test_blocked_on_low_score() -> None:
    result = check_application_quality(
        job=make_job(),
        tailored_cv=make_cv(),
        cover_letter="Good cover letter.",
        score=make_score(total=50),
        config=make_config(threshold=62),
    )
    assert result.decision == GateDecision.BLOCKED
    assert result.is_approved is False
    assert any("below threshold" in r for r in result.blocking_reasons)


def test_blocked_on_no_sponsorship() -> None:
    job = make_job("ML Engineer. No sponsorship available. US citizens only.")
    config = make_config()
    config.visa.enabled = True
    config.visa.skip_no_sponsorship = True
    result = check_application_quality(
        job=job,
        tailored_cv=make_cv(),
        cover_letter="Strong application.",
        score=make_score(75),
        config=config,
    )
    assert result.decision == GateDecision.BLOCKED
    assert any("sponsorship" in r.lower() for r in result.blocking_reasons)


def test_visa_check_skipped_when_disabled() -> None:
    job = make_job("No sponsorship. Citizens only.")
    config = make_config()
    config.visa.enabled = False
    result = check_application_quality(
        job=job,
        tailored_cv=make_cv(),
        cover_letter="Good application.",
        score=make_score(75),
        config=config,
    )
    assert result.decision != GateDecision.BLOCKED or all(
        "sponsorship" not in r for r in result.blocking_reasons
    )


def test_warning_on_banned_phrase() -> None:
    result = check_application_quality(
        job=make_job(),
        tailored_cv=make_cv(),
        cover_letter="I am passionate about machine learning.",
        score=make_score(75),
        config=make_config(),
    )
    assert result.has_warnings is True
    assert any("passionate" in w for w in result.warnings)


def test_warning_on_long_cover_letter() -> None:
    long_letter = "ML experience. " * 200  # 400 words — over 350 threshold
    result = check_application_quality(
        job=make_job(),
        tailored_cv=make_cv(),
        cover_letter=long_letter,
        score=make_score(75),
        config=make_config(),
    )
    assert any("word" in w.lower() for w in result.warnings)


def test_warning_on_senior_signal() -> None:
    job = make_job("We need 10+ years of ML experience. Staff engineer level.")
    result = check_application_quality(
        job=job,
        tailored_cv=make_cv(),
        cover_letter="Good application.",
        score=make_score(75),
        config=make_config(),
    )
    assert any("senior" in w.lower() or "staff" in w.lower() for w in result.warnings)


def test_warning_on_low_confidence() -> None:
    result = check_application_quality(
        job=make_job(),
        tailored_cv=make_cv(),
        cover_letter="Good application.",
        score=make_score(75, confidence=0.3),
        config=make_config(),
    )
    assert any("confidence" in w.lower() for w in result.warnings)


def test_warning_on_missing_cv_field() -> None:
    cv = {"personal": {"name": "Test"}}
    result = check_application_quality(
        job=make_job(),
        tailored_cv=cv,
        cover_letter="Good application.",
        score=make_score(75),
        config=make_config(),
    )
    assert any(
        "email" in w.lower() or "phone" in w.lower() or "missing" in w.lower()
        for w in result.warnings
    )


def test_gate_decision_approved_has_recommendation() -> None:
    result = check_application_quality(
        job=make_job(),
        tailored_cv=make_cv(),
        cover_letter="Concise strong letter.",
        score=make_score(75),
        config=make_config(),
    )
    assert result.recommendation != ""


def test_blocked_sets_is_approved_false() -> None:
    result = check_application_quality(
        job=make_job(),
        tailored_cv=make_cv(),
        cover_letter="",
        score=make_score(40),
        config=make_config(threshold=62),
    )
    assert result.is_approved is False


def test_run_quality_check_no_cv(tmp_path, monkeypatch) -> None:
    from nj.cli.cmd_quality import run_quality_check

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_quality.console", c):
        run_quality_check(Config(), db_path=str(tmp_path / "nj.db"))
    assert "cv_base.json" in buf.getvalue()


# --- the gate and the classifier must agree --------------------------------
#
# The gate carried its own NO_SPONSORSHIP_SIGNALS list containing
# "must be authorized" — the exact phrase visa_filter.py removed as
# OPT-satisfiable. Because the gate runs after tailoring and rendering, a false
# block here discards two LLM calls, a reviewer pass and a tectonic compile,
# and records the job as FAILED.


def _gate(description: str):
    from nj.models.config import Config
    from nj.scoring.quality_gate import check_application_quality

    config = Config()
    job = make_job()
    job.description = description
    score = make_score()
    score.total_score = config.scoring.threshold + 10
    return check_application_quality(
        job=job,
        tailored_cv={"personal": {"name": "A", "email": "a@b.c", "phone": "1", "linkedin": "l"}},
        cover_letter="A specific letter about the role and the team's work.",
        score=score,
        config=config,
    )


def test_must_be_authorized_alone_no_longer_blocks() -> None:
    """Satisfied by OPT, and present in nearly every US posting."""
    result = _gate("You must be authorized to work in the United States at time of hire.")
    assert result.decision is not GateDecision.BLOCKED


def test_a_sponsoring_employer_that_also_says_must_be_authorized_passes() -> None:
    result = _gate(
        "We sponsor H-1B visas for qualified candidates. "
        "Must be authorized to work in the US at time of hire."
    )
    assert result.decision is not GateDecision.BLOCKED


def test_an_actual_refusal_still_blocks() -> None:
    result = _gate("We are unable to offer visa sponsorship for this position.")
    assert result.decision is GateDecision.BLOCKED
    assert any("sponsor" in r.lower() for r in result.blocking_reasons)


def test_citizens_only_still_blocks() -> None:
    result = _gate("This role is open to US citizens only.")
    assert result.decision is GateDecision.BLOCKED


def test_the_gate_reports_the_phrase_that_decided_it() -> None:
    """The evidence, not just the verdict — a wrong block has to be diagnosable."""
    result = _gate("We do not sponsor employment visas, now or in the future.")
    assert result.blocking_reasons
    assert "sponsor" in result.blocking_reasons[0].lower()


def test_visa_checking_can_be_turned_off() -> None:
    from nj.models.config import Config
    from nj.scoring.quality_gate import check_application_quality

    config = Config()
    config.visa.skip_no_sponsorship = False
    job = make_job()
    job.description = "US citizens only."
    score = make_score()
    score.total_score = config.scoring.threshold + 10
    result = check_application_quality(
        job=job,
        tailored_cv={"personal": {"name": "A", "email": "a@b.c", "phone": "1", "linkedin": "l"}},
        cover_letter="A specific letter.",
        score=score,
        config=config,
    )
    assert result.decision is not GateDecision.BLOCKED
