"""Unit tests for nj enrich command."""

from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO
from unittest.mock import patch

from nj.models.config import Config


def test_run_enrich_no_url(tmp_path, monkeypatch):
    from rich.console import Console

    from nj.cli.cmd_enrich import run_enrich

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_enrich.console", c):
        run_enrich(Config(), url=None)
    assert "Usage" in buf.getvalue()


def test_extract_title_company_linkedin():
    from nj.cli.cmd_enrich import _extract_title_company

    html = "<title>ML Engineer at Google | LinkedIn</title>"
    title, company = _extract_title_company(html, "https://linkedin.com/jobs/view/123")
    assert "ML Engineer" in title
    assert len(title) > 0


def test_extract_title_company_at_pattern():
    from nj.cli.cmd_enrich import _extract_title_company

    html = "<title>Senior ML Engineer at OpenAI</title>"
    title, company = _extract_title_company(html, "https://openai.com/careers")
    assert "ML Engineer" in title or "Senior" in title
    assert "OpenAI" in company or len(company) > 0


def test_extract_title_fallback():
    from nj.cli.cmd_enrich import _extract_title_company

    html = "<html><body>No title here</body></html>"
    title, company = _extract_title_company(html, "https://example.com/job")
    assert len(title) > 0
    assert len(company) > 0


def test_display_enrich_report_renders(tmp_path):
    from rich.console import Console

    from nj.cli.cmd_enrich import _display_enrich_report
    from nj.models.job import Job, JobStatus, VisaLabel

    job = Job(
        id="test",
        title="ML Engineer",
        company="Acme",
        url="https://example.com",
        description="PyTorch role. H1B sponsor.",
        location="Remote",
        source="direct",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash="abc",
    )
    enrichment = {
        "sponsorship": {"probability": 0.82, "tier": "LIKELY_SPONSOR"},
        "salary": {
            "predicted_salary": 165000,
            "range": {"low": 140000, "high": 190000},
        },
        "semantic": {"score": 74.2, "interpretation": "Strong semantic match"},
        "uscis_profile": {
            "total_petitions": 450,
            "approval_rate": 93.2,
            "ml_ai_petitions": 87,
            "sponsor_tier": "STRONG",
        },
    }
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_enrich.console", c):
        _display_enrich_report(job, enrichment, Config())
    output = buf.getvalue()
    assert "82" in output or "82%" in output
    assert "165" in output or "165,000" in output
    assert "74" in output


def test_fetch_job_from_url_network_error():
    import httpx

    from nj.cli.cmd_enrich import _fetch_job_from_url

    with patch("httpx.get", side_effect=httpx.ConnectError("failed")):
        result = _fetch_job_from_url("https://example.com/job", Config())
    assert result is None


def test_enrich_command_registered():
    from nj.cli.app import app

    callback_names = [c.callback.__name__ for c in app.registered_commands if c.callback]
    assert "enrich" in callback_names
