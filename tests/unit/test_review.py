from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from nj.cli.cmd_review import (
    _print_session_summary,
    _render_job_panel,
    _render_score_table,
    _score_color,
    run_review,
)
from nj.models.job import Job, JobStatus, VisaLabel
from nj.models.score import ScoreCategory, ScoreResult, SubScore


def make_job(**kwargs) -> Job:
    defaults = dict(
        id="job-1",
        title="ML Engineer",
        company="Acme",
        url="https://example.com/jobs/1",
        description="We are looking for an ML Engineer with PyTorch experience.",
        location="San Francisco, CA",
        source="linkedin",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.PENDING_REVIEW,
        description_hash="abc123",
    )
    defaults.update(kwargs)
    return Job(**defaults)


def make_score(**kwargs) -> ScoreResult:
    sub_scores = [
        SubScore(
            category=ScoreCategory.SKILLS_MATCH, score=80, weight=0.30, rationale="Strong match"
        ),
        SubScore(
            category=ScoreCategory.SPONSORSHIP_COMPAT,
            score=90,
            weight=0.15,
            rationale="Confirmed sponsor",
        ),
    ]
    defaults = dict(
        job_id="job-1",
        total_score=80,
        confidence=0.9,
        matched_skills=["PyTorch", "Python"],
        missing_skills=["Kubernetes"],
        recommended_emphasis=["deep learning", "computer vision"],
        overall_rationale="Good fit overall.",
        sub_scores=sub_scores,
        scored_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    return ScoreResult(**defaults)


# --- _score_color ---


def test_score_color_green_at_75() -> None:
    assert _score_color(75) == "green"


def test_score_color_green_above_75() -> None:
    assert _score_color(90) == "green"


def test_score_color_yellow_at_60() -> None:
    assert _score_color(60) == "yellow"


def test_score_color_yellow_at_74() -> None:
    assert _score_color(74) == "yellow"


def test_score_color_red_below_60() -> None:
    assert _score_color(59) == "red"


def test_score_color_red_at_zero() -> None:
    assert _score_color(0) == "red"


# --- _render_score_table ---


def test_render_score_table_returns_table() -> None:
    from rich.table import Table

    result = _render_score_table(make_score())
    assert isinstance(result, Table)


def test_render_score_table_has_rows() -> None:
    score = make_score()
    table = _render_score_table(score)
    assert table.row_count == len(score.sub_scores)


# --- _render_job_panel ---


def test_render_job_panel_returns_panel() -> None:
    from rich.panel import Panel

    panel = _render_job_panel(make_job(), make_score(), 1, 5)
    assert isinstance(panel, Panel)


def test_render_job_panel_contains_job_title() -> None:
    from io import StringIO

    from rich.console import Console

    job = make_job()
    score = make_score()
    panel = _render_job_panel(job, score, 1, 5)
    buf = StringIO()
    console = Console(file=buf, highlight=False)
    console.print(panel)
    output = buf.getvalue()
    assert job.title in output


def test_render_job_panel_shows_score() -> None:
    from io import StringIO

    from rich.console import Console

    score = make_score(total_score=80)
    panel = _render_job_panel(make_job(), score, 1, 5)
    buf = StringIO()
    console = Console(file=buf, highlight=False)
    console.print(panel)
    assert "80" in buf.getvalue()


# --- _print_session_summary ---


def test_print_session_summary_renders(capsys) -> None:
    from io import StringIO

    from rich.console import Console

    buf = StringIO()
    with patch("nj.cli.cmd_review.console", Console(file=buf, highlight=False)):
        _print_session_summary(applied=2, skipped=3, labeled=1, total=10)
    output = buf.getvalue()
    assert "2" in output
    assert "3" in output
    assert "Remaining" in output


# --- run_review ---


def test_run_review_exits_on_empty_queue() -> None:
    from nj.models.config import Config

    config = MagicMock(spec=Config)
    with (
        patch("nj.cli.cmd_review.JobRepo") as mock_job_repo_cls,
        patch("nj.cli.cmd_review.ScoreRepo"),
        patch("nj.cli.cmd_review.LabelRepo"),
    ):
        mock_job_repo = MagicMock()
        mock_job_repo.get_jobs.return_value = []
        mock_job_repo_cls.return_value = mock_job_repo

        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        with patch("nj.cli.cmd_review.console", Console(file=buf, highlight=False)):
            run_review(config=config, db_path=":memory:", limit=50)

    output = buf.getvalue()
    assert "No jobs pending review" in output


# --- approving must not claim an artifact that does not exist --------------
#
# Approving wrote JobStatus.TAILORED, which asserts a rendered CV is on disk.
# Nothing was generated, so following the documented review loop left rows
# labelled `tailored` and an empty output/ — and `nj quality`, which selects on
# TAILORED, then tried to gate applications that had never been produced.


def _review_with_keys(keys, job=None, score=None):
    """Drive run_review through a scripted sequence of keypresses."""
    job = job or make_job()
    score = score or make_score()

    job_repo = MagicMock()
    job_repo.get_jobs.return_value = [job]
    score_repo = MagicMock()
    score_repo.get_score.return_value = score

    with (
        patch("nj.cli.cmd_review.JobRepo", return_value=job_repo),
        patch("nj.cli.cmd_review.ScoreRepo", return_value=score_repo),
        patch("nj.cli.cmd_review.LabelRepo", return_value=MagicMock()),
        patch("nj.cli.cmd_review._get_keypress", side_effect=list(keys)),
    ):
        run_review(config=MagicMock(), db_path=":memory:")
    return job_repo


def test_approving_does_not_write_tailored() -> None:
    job_repo = _review_with_keys(["a"])
    written = [c.args[1] for c in job_repo.update_job_status.call_args_list]
    assert JobStatus.TAILORED not in written


def test_approving_writes_approved_pending_tailoring() -> None:
    job_repo = _review_with_keys(["a"])
    job_repo.update_job_status.assert_called_once_with(
        "job-1", JobStatus.APPROVED_PENDING_TAILORING
    )


def test_the_status_written_matches_the_artifacts_that_exist(tmp_path) -> None:
    """The invariant: TAILORED may only be written when a CV was rendered.

    Approving renders nothing, so no path through nj review may produce it.
    """
    import inspect

    from nj.cli import cmd_review

    source = inspect.getsource(cmd_review)
    assert "JobStatus.TAILORED" not in source


def test_approving_tells_you_it_generated_nothing(capsys) -> None:
    _review_with_keys(["a"])
    out = capsys.readouterr().out
    assert "Nothing generated yet" in out
    assert "nj tailor --job-id" in out


def test_the_session_ends_by_naming_the_tailor_command(capsys) -> None:
    """Approving is a decision, not an artifact — the session has to say so."""
    _review_with_keys(["a"])
    out = capsys.readouterr().out
    assert "nothing is generated yet" in out.lower()


def test_skipping_still_writes_skipped() -> None:
    job_repo = _review_with_keys(["s"])
    job_repo.update_job_status.assert_called_once_with("job-1", JobStatus.SKIPPED)


def test_a_session_with_no_approvals_prints_no_next_steps(capsys) -> None:
    _review_with_keys(["s"])
    out = capsys.readouterr().out
    assert "nj tailor --job-id" not in out


def test_approved_pending_tailoring_is_a_real_status() -> None:
    assert JobStatus.APPROVED_PENDING_TAILORING.value == "approved_pending_tailoring"
    assert JobStatus("approved_pending_tailoring") is JobStatus.APPROVED_PENDING_TAILORING


def test_approved_jobs_leave_the_review_queue() -> None:
    """The queue selects PENDING_REVIEW; the new status is not that."""
    assert JobStatus.APPROVED_PENDING_TAILORING is not JobStatus.PENDING_REVIEW


def test_quality_gate_still_selects_only_tailored_jobs() -> None:
    """nj quality checks rendered applications. An approval has no files to check."""
    import inspect

    from nj.cli import cmd_quality

    source = inspect.getsource(cmd_quality)
    assert "JobStatus.TAILORED" in source
    assert "JobStatus.APPROVED_PENDING_TAILORING" not in source
