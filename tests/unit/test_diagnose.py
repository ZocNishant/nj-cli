from __future__ import annotations

import json
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from nj.diagnostics.engine import _parse_diagnosis
from nj.diagnostics.renderer import _build_diagnosis_latex
from nj.models.config import Config
from nj.models.diagnosis import DiagnosisResult, HealthLevel, Severity
from nj.prompts.diagnosis_v1 import PROMPT_VERSION, build_user_prompt
from nj.providers.base import LLMResponse


def make_cv() -> dict:
    return {
        "personal": {
            "name": "Test User",
            "visa_note": "OPT eligible",
            "graduation_date": "December 2026",
        },
        "skills": {
            "ml_frameworks": ["PyTorch", "TensorFlow"],
            "security_tools": ["Wireshark"],
        },
        "experience": [
            {
                "id": "usd",
                "title": "IT Assistant",
                "company": "USD",
                "start": "2026",
                "end": "Present",
                "status": "active",
                "bullets": ["Managed network."],
                "tags": ["it"],
            }
        ],
        "projects": [
            {
                "id": "testvision",
                "name": "TestVision",
                "anchor": True,
                "tech": ["PyTorch"],
                "bullets": ["Achieved 95% accuracy."],
                "priority": 1,
            }
        ],
        "education": [
            {
                "degree": "MS CS",
                "institution": "USD",
                "end": "Dec 2026",
                "courses": ["ML"],
            }
        ],
    }


def make_diagnosis_data() -> dict:
    return {
        "overall_health": "moderate",
        "critical_issues": [
            {
                "section": "experience",
                "issue": "IT roles dominate — reads as sysadmin not ML engineer",
                "severity": "high",
                "fix": "Lead each bullet with ML outcome not IT task",
            },
            {
                "section": "skills",
                "issue": "Security tools irrelevant for ML roles",
                "severity": "medium",
                "fix": "Remove security tools section for ML applications",
            },
        ],
        "hidden_strengths": [
            "TestVision shows rare medical domain + CV engineering combination"
        ],
        "weak_sections": ["experience", "summary"],
        "strong_sections": ["projects", "skills"],
        "recruiter_first_impression": (
            "Sees an IT person trying to break into ML. "
            "TestVision saves it from the reject pile."
        ),
        "ats_concerns": ["Employment gap may trigger ATS filters"],
        "positioning_mismatch": (
            "CV positions as IT professional with ML hobby. "
            "Target roles want ML engineer with strong projects."
        ),
        "score_pattern_analysis": "Experience relevance dragging scores below threshold.",
        "top_recommendation": "Rewrite experience bullets to emphasize any ML work done.",
    }


def test_prompt_version() -> None:
    assert PROMPT_VERSION == "diagnosis_v1"


def test_build_user_prompt_includes_roles() -> None:
    prompt = build_user_prompt(
        cv_base=make_cv(),
        target_roles=["ML Engineer", "CV Engineer"],
    )
    assert "ML Engineer" in prompt
    assert "CV Engineer" in prompt


def test_build_user_prompt_includes_cv() -> None:
    prompt = build_user_prompt(
        cv_base=make_cv(),
        target_roles=["ML Engineer"],
    )
    assert "TestVision" in prompt
    assert "PyTorch" in prompt


def test_build_user_prompt_includes_score_context() -> None:
    scores = [
        {
            "total_score": 58,
            "sub_scores": [
                {"category": "skills_match", "score": 80},
                {"category": "experience_relevance", "score": 40},
            ],
        }
    ]
    prompt = build_user_prompt(
        cv_base=make_cv(),
        target_roles=["ML Engineer"],
        recent_scores=scores,
    )
    assert "58" in prompt or "58.0" in prompt
    assert "experience_relevance" in prompt


def test_parse_diagnosis_valid() -> None:
    result = _parse_diagnosis(make_diagnosis_data())
    assert result.overall_health == HealthLevel.MODERATE
    assert len(result.critical_issues) == 2
    assert result.critical_issues[0].severity == Severity.HIGH
    assert result.critical_issues[1].severity == Severity.MEDIUM
    assert "TestVision" in result.hidden_strengths[0]


def test_parse_diagnosis_sorts_by_severity() -> None:
    data = make_diagnosis_data()
    data["critical_issues"] = [
        {"section": "b", "issue": "low issue", "severity": "low", "fix": "fix b"},
        {"section": "a", "issue": "high issue", "severity": "high", "fix": "fix a"},
    ]
    result = _parse_diagnosis(data)
    assert result.critical_issues[0].severity == Severity.HIGH
    assert result.critical_issues[1].severity == Severity.LOW


def test_parse_diagnosis_handles_unknown_health() -> None:
    data = make_diagnosis_data()
    data["overall_health"] = "excellent"
    result = _parse_diagnosis(data)
    assert result.overall_health == HealthLevel.MODERATE


def test_parse_diagnosis_skips_bad_issues() -> None:
    data = make_diagnosis_data()
    data["critical_issues"].append(
        {"section": "x", "issue": "bad", "severity": "invalid_value", "fix": "fix"}
    )
    result = _parse_diagnosis(data)
    assert len(result.critical_issues) == 2


def test_build_diagnosis_latex_sections() -> None:
    result = DiagnosisResult(**_parse_diagnosis(make_diagnosis_data()).model_dump())
    latex = _build_diagnosis_latex(result, make_cv())
    assert "CV Diagnosis" in latex
    assert "Critical Issues" in latex
    assert "Recruiter First Impression" in latex
    assert "Hidden Strengths" in latex
    assert "Positioning Analysis" in latex


def test_build_diagnosis_latex_top_recommendation() -> None:
    result = _parse_diagnosis(make_diagnosis_data())
    latex = _build_diagnosis_latex(result, make_cv())
    assert "Top recommendation" in latex
    assert "Rewrite experience" in latex


def test_build_diagnosis_latex_health_color() -> None:
    result = _parse_diagnosis(make_diagnosis_data())
    latex = _build_diagnosis_latex(result, make_cv())
    assert "orange" in latex


@pytest.mark.asyncio
async def test_diagnose_cv_calls_provider() -> None:
    from nj.diagnostics.engine import diagnose_cv

    cv = make_cv()
    config = Config()
    mock_provider = MagicMock()
    mock_provider.name.return_value = "claude"
    mock_provider.complete = AsyncMock(
        return_value=LLMResponse(
            content=json.dumps(make_diagnosis_data()),
            provider="claude",
            model="claude-sonnet-4-20250514",
            input_tokens=1000,
            output_tokens=500,
            latency_ms=2000,
        )
    )
    result = await diagnose_cv(cv, config, mock_provider)
    assert result.overall_health == HealthLevel.MODERATE
    assert len(result.critical_issues) == 2
    mock_provider.complete.assert_called_once()


@pytest.mark.asyncio
async def test_diagnose_cv_retries_on_bad_json() -> None:
    from nj.diagnostics.engine import diagnose_cv

    cv = make_cv()
    config = Config()
    mock_provider = MagicMock()
    mock_provider.name.return_value = "claude"
    mock_provider.complete = AsyncMock(
        side_effect=[
            LLMResponse(
                content="not json",
                provider="claude",
                model="test",
                input_tokens=10,
                output_tokens=5,
                latency_ms=100,
            ),
            LLMResponse(
                content=json.dumps(make_diagnosis_data()),
                provider="claude",
                model="test",
                input_tokens=10,
                output_tokens=5,
                latency_ms=100,
            ),
        ]
    )
    result = await diagnose_cv(cv, config, mock_provider)
    assert result.overall_health == HealthLevel.MODERATE
    assert mock_provider.complete.call_count == 2


def test_run_diagnose_no_cv(tmp_path, monkeypatch) -> None:
    from nj.cli.cmd_diagnose import run_diagnose

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diagnose.console", c):
        run_diagnose(Config(), db_path=str(tmp_path / "nj.db"))
    assert "cv_base.json" in buf.getvalue()
