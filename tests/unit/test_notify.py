from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nj.models.config import NotifyConfig
from nj.notify.digest import format_summary_table
from nj.notify.email import EmailNotifier


def make_config(**kwargs) -> NotifyConfig:
    defaults = {
        "email_to": "test@example.com",
        "provider": "smtp",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "sender@gmail.com",
        "smtp_password": "app-password",
    }
    defaults.update(kwargs)
    return NotifyConfig(**defaults)


def test_send_returns_false_when_no_recipient() -> None:
    notifier = EmailNotifier(make_config(email_to=""))
    result = notifier.send_application_email(
        job_title="ML Engineer",
        company="Acme",
        job_url="https://example.com",
        score=75,
        confidence=0.85,
        matched_skills=["PyTorch"],
        missing_skills=[],
        visa_label="confirmed",
        visa_notes="H1B offered",
    )
    assert result is False


def test_send_application_email_via_smtp() -> None:
    notifier = EmailNotifier(make_config())
    with patch("nj.notify.email.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        result = notifier.send_application_email(
            job_title="ML Engineer",
            company="Acme",
            job_url="https://example.com",
            score=75,
            confidence=0.85,
            matched_skills=["PyTorch"],
            missing_skills=["Kubernetes"],
            visa_label="confirmed",
            visa_notes="H1B offered",
        )
    assert result is True
    mock_server.send_message.assert_called_once()


def test_send_application_email_attaches_cv(tmp_path: Path) -> None:
    cv_file = tmp_path / "cv.pdf"
    cv_file.write_bytes(b"fake pdf content")
    notifier = EmailNotifier(make_config())
    with patch("nj.notify.email.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        result = notifier.send_application_email(
            job_title="ML Engineer",
            company="Acme",
            job_url="https://example.com",
            score=75,
            confidence=0.85,
            matched_skills=["PyTorch"],
            missing_skills=[],
            visa_label="confirmed",
            visa_notes="H1B offered",
            cv_path=str(cv_file),
        )
    assert result is True


def test_send_returns_false_on_smtp_error() -> None:
    notifier = EmailNotifier(make_config())
    with patch("nj.notify.email.smtplib.SMTP", side_effect=Exception("connection refused")):
        result = notifier.send_application_email(
            job_title="ML Engineer",
            company="Acme",
            job_url="https://example.com",
            score=75,
            confidence=0.85,
            matched_skills=[],
            missing_skills=[],
            visa_label="unknown",
            visa_notes="",
        )
    assert result is False


def test_daily_summary_empty() -> None:
    result = format_summary_table([])
    assert "No applications" in result


def test_daily_summary_formats_table() -> None:
    apps = [
        {"score": 75, "status": "submitted", "company": "Acme",
         "title": "ML Engineer", "visa_label": "confirmed"},
        {"score": 62, "status": "submitted", "company": "Beta Corp",
         "title": "CV Engineer", "visa_label": "unknown"},
    ]
    result = format_summary_table(apps)
    assert "Acme" in result
    assert "75" in result
    assert "Average score" in result


def test_daily_summary_sorted_by_score_descending() -> None:
    apps = [
        {"score": 60, "status": "submitted", "company": "Low",
         "title": "Role A", "visa_label": "unknown"},
        {"score": 90, "status": "submitted", "company": "High",
         "title": "Role B", "visa_label": "confirmed"},
    ]
    result = format_summary_table(apps)
    assert result.index("High") < result.index("Low")


def test_cover_letter_fallback_contains_gastrovision() -> None:
    from nj.models.job import Job, JobStatus, VisaLabel
    from nj.models.score import ScoreResult
    from nj.tailoring.cover_letter import _fallback_cover_letter

    job = Job(
        id="test",
        title="ML Engineer",
        company="Acme",
        url="https://example.com",
        description="ML role",
        location="USA",
        source="indeed",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash="abc",
    )
    score = ScoreResult(
        job_id="test",
        total_score=75,
        confidence=0.8,
        matched_skills=["PyTorch"],
        scored_at=datetime.now(UTC),
    )
    result = _fallback_cover_letter(job, score)
    assert "GastroVision" in result
    assert "96.11%" in result
    assert "Nishant Joshi" in result
    assert "OPT" in result
