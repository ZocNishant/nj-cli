"""Tests for the generalized nj init wizard."""

from __future__ import annotations

import json
from unittest.mock import patch

from nj.cli.cmd_init import (
    _build_blank_cv,
    _extract_cv_from_pdf,
    _step_career,
    _step_notifications,
    _step_preferences,
    _step_visa,
)


def test_build_blank_cv_creates_valid_structure(tmp_path):
    personal = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "",
        "location": "NYC, USA",
        "linkedin": "",
        "github": "",
        "website": "",
        "graduation_date": "",
    }
    career = {
        "career_field": "software_engineering",
        "seniority": "mid",
        "target_roles": ["Software Engineer"],
        "target_country": "USA",
    }
    visa = {"enabled": False, "status": "not_applicable", "work_authorization": "Authorized"}
    cv_path = tmp_path / "cv_base.json"
    _build_blank_cv(personal, career, visa, cv_path)
    assert cv_path.exists()
    with open(cv_path) as f:
        cv = json.load(f)
    assert "personal" in cv
    assert "skills" in cv
    assert "experience" in cv
    assert "projects" in cv
    assert "education" in cv
    assert cv["cv_version"] == "1.0"


def test_build_blank_cv_includes_personal_info(tmp_path):
    personal = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
        "location": "London, UK",
        "linkedin": "",
        "github": "",
        "website": "",
        "graduation_date": "May 2024",
    }
    career = {
        "career_field": "ml_ai",
        "seniority": "junior",
        "target_roles": ["ML Engineer"],
        "target_country": "UK",
    }
    visa = {"enabled": True, "status": "opt", "work_authorization": "OPT"}
    cv_path = tmp_path / "cv_base.json"
    _build_blank_cv(personal, career, visa, cv_path)
    with open(cv_path) as f:
        cv = json.load(f)
    assert cv["personal"]["name"] == "Jane Doe"
    assert cv["personal"]["email"] == "jane@example.com"
    assert cv["personal"]["graduation_date"] == "May 2024"
    assert cv["personal"]["visa_status"] == "opt"
    assert cv["career_field"] == "ml_ai"
    assert cv["seniority"] == "junior"
    assert cv["target_roles"] == ["ML Engineer"]


def test_build_blank_cv_sets_career_field(tmp_path):
    personal = {
        "name": "Dev User",
        "email": "dev@example.com",
        "phone": "",
        "location": "",
        "linkedin": "",
        "github": "",
        "website": "",
        "graduation_date": "",
    }
    career = {
        "career_field": "data_science",
        "seniority": "senior",
        "target_roles": ["Data Scientist"],
        "target_country": "USA",
    }
    visa = {"enabled": False, "status": "not_applicable", "work_authorization": ""}
    cv_path = tmp_path / "cv_base.json"
    _build_blank_cv(personal, career, visa, cv_path)
    with open(cv_path) as f:
        cv = json.load(f)
    assert cv["career_field"] == "data_science"
    assert cv["seniority"] == "senior"


def test_step_visa_no_sponsorship_needed():
    with patch("nj.cli.cmd_init.Confirm.ask", return_value=False):
        result = _step_visa()
    assert result["enabled"] is False
    assert result["work_authorization"] == "Authorized to work"


def test_step_visa_with_h1b_needed():
    with (
        patch("nj.cli.cmd_init.Confirm.ask", side_effect=[True, True, True]),
        patch("nj.cli.cmd_init.Prompt.ask", side_effect=["h1b", "H1B — open to sponsorship"]),
    ):
        result = _step_visa()
    assert result["enabled"] is True
    assert result["status"] == "h1b"
    assert result["h1b_future"] is True
    assert "include_keywords" in result
    assert "exclude_keywords" in result


def test_step_career_uses_default_roles():
    with (
        patch("nj.cli.cmd_init.Prompt.ask", side_effect=["ml_ai", "mid", "USA"]),
        patch("nj.cli.cmd_init.Confirm.ask", side_effect=[False, False]),
    ):
        result = _step_career()
    assert result["career_field"] == "ml_ai"
    assert result["seniority"] == "mid"
    assert len(result["target_roles"]) > 0
    assert result["target_country"] == "USA"


def test_step_career_custom_roles():
    with (
        patch(
            "nj.cli.cmd_init.Prompt.ask",
            side_effect=["software_engineering", "senior", "ML Engineer, AI Engineer", "Germany"],
        ),
        patch("nj.cli.cmd_init.Confirm.ask", side_effect=[True, False]),
    ):
        result = _step_career()
    assert "ML Engineer" in result["target_roles"]
    assert "AI Engineer" in result["target_roles"]
    assert result["target_country"] == "Germany"


def test_step_preferences_parses_exclusions():
    with patch("nj.cli.cmd_init.Prompt.ask", return_value="10+ years, Director Level, VP"):
        result = _step_preferences({"career_field": "software_engineering"})
    assert "10+ years" in result["keywords_exclude"]
    assert "Director Level" in result["keywords_exclude"]
    assert "VP" in result["keywords_exclude"]


def test_step_notifications_skip():
    with patch("nj.cli.cmd_init.Confirm.ask", return_value=False):
        result = _step_notifications({})
    assert result["email_to"] == ""
    assert result["provider"] == "smtp"


def test_step_notifications_smtp_setup():
    env: dict = {}
    with (
        patch("nj.cli.cmd_init.Confirm.ask", return_value=True),
        patch(
            "nj.cli.cmd_init.Prompt.ask",
            side_effect=[
                "smtp",
                "user@example.com",
                "smtp.gmail.com",
                "587",
                "user@example.com",
                "apppassword",
            ],
        ),
    ):
        result = _step_notifications(env)
    assert result["email_to"] == "user@example.com"
    assert result["provider"] == "smtp"
    assert result["smtp_host"] == "smtp.gmail.com"


def test_extract_cv_from_pdf_falls_back_on_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cv").mkdir()
    personal = {
        "name": "Test",
        "email": "t@t.com",
        "phone": "",
        "location": "",
        "linkedin": "",
        "github": "",
        "website": "",
        "graduation_date": "",
    }
    career = {
        "career_field": "software_engineering",
        "seniority": "mid",
        "target_roles": [],
        "target_country": "USA",
    }
    visa = {"status": "not_applicable", "work_authorization": ""}
    with patch("anthropic.Anthropic", side_effect=Exception("no API")):
        _extract_cv_from_pdf(str(tmp_path / "nonexistent.pdf"), "fake-key", personal, career, visa)
    assert (tmp_path / "cv" / "cv_base.json").exists()
