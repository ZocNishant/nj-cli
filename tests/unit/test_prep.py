from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nj.models.config import Config
from nj.models.job import Job, JobStatus, VisaLabel
from nj.prompts.prep_v1 import PROMPT_VERSION, build_user_prompt
from nj.providers.base import LLMResponse
from nj.tailoring.prep_generator import _build_prep_latex


def make_job() -> Job:
    return Job(
        id="test-id",
        title="ML Engineer",
        company="Acme Corp",
        url="https://example.com",
        description="PyTorch deep learning role. H1B sponsorship.",
        location="San Francisco",
        source="remoteok",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.APPLIED,
        description_hash="abc",
    )


def make_cv() -> dict:
    return {
        "personal": {
            "name": "Test User",
            "visa_note": "OPT eligible",
            "graduation_date": "December 2026",
        },
        "skills": {
            "ml_frameworks": ["PyTorch", "TensorFlow"],
        },
        "experience": [
            {
                "title": "ML Intern",
                "company": "Test Corp",
                "start": "June 2026",
                "end": "Present",
                "status": "incoming",
                "bullets": [],
            }
        ],
        "projects": [
            {
                "name": "TestVision",
                "anchor": True,
                "tech": ["PyTorch"],
                "bullets": ["Achieved 95% accuracy."],
                "priority": 1,
            }
        ],
        "education": [
            {
                "degree": "MS Computer Science",
                "institution": "Test University",
                "end": "December 2026",
                "courses": ["Machine Learning"],
            }
        ],
        "research_interests": ["Computer Vision"],
    }


def make_prep_data() -> dict:
    return {
        "company_brief": {
            "what_they_do": "AI company building ML tools.",
            "why_hiring": "Need ML engineer for core product.",
            "tech_stack_mentioned": ["PyTorch", "Docker"],
            "culture_signals": ["fast-paced", "research-driven"],
        },
        "technical_questions": [
            {
                "question": "Explain your experience with PyTorch.",
                "why_asked": "Core framework for the role.",
                "your_answer": "Used PyTorch in TestVision project.",
                "confidence": "high",
            },
            {
                "question": "How do you handle class imbalance?",
                "why_asked": "Common ML challenge.",
                "your_answer": "Used weighted loss functions.",
                "confidence": "high",
            },
        ],
        "behavioural_questions": [
            {
                "question": "Tell me about a challenging ML project.",
                "framework": "STAR",
                "situation": "TestVision had severe class imbalance.",
                "task": "Improve model performance.",
                "talking_points": ["Used weighted loss", "Improved 27%"],
            }
        ],
        "story_bank": [
            {
                "story_title": "TestVision Achievement",
                "opening_line": "I built a medical image classifier.",
                "jd_requirement_addressed": "Computer vision experience",
                "key_metrics": ["95% accuracy"],
            }
        ],
        "quick_reference": {
            "role_in_one_sentence": "ML engineer building AI products.",
            "top_3_they_want": ["PyTorch", "CV experience", "Docker"],
            "top_3_you_bring": ["PyTorch", "TestVision", "Research"],
            "biggest_gap": "No production deployment experience.",
            "gap_framing": "Currently building deployed ML services.",
            "research_before_call": ["Recent Acme blog posts"],
        },
    }


def test_prompt_version_is_string() -> None:
    assert isinstance(PROMPT_VERSION, str)
    assert PROMPT_VERSION == "prep_v1"


def test_build_user_prompt_includes_company() -> None:
    prompt = build_user_prompt(
        job_title="ML Engineer",
        job_company="Acme Corp",
        job_description="PyTorch role",
        cv_base=make_cv(),
    )
    assert "Acme Corp" in prompt
    assert "ML Engineer" in prompt


def test_build_user_prompt_includes_cv_data() -> None:
    prompt = build_user_prompt(
        job_title="ML Engineer",
        job_company="Acme",
        job_description="PyTorch role",
        cv_base=make_cv(),
    )
    assert "TestVision" in prompt
    assert "PyTorch" in prompt


def test_build_user_prompt_includes_score_context() -> None:
    score = {
        "total_score": 78,
        "matched_skills": ["PyTorch"],
        "missing_skills": ["Kubernetes"],
        "overall_rationale": "Good match.",
    }
    prompt = build_user_prompt(
        job_title="ML Engineer",
        job_company="Acme",
        job_description="PyTorch role",
        cv_base=make_cv(),
        score_result=score,
    )
    assert "78" in prompt
    assert "PyTorch" in prompt
    assert "Kubernetes" in prompt


def test_build_prep_latex_contains_sections() -> None:
    latex = _build_prep_latex(make_prep_data(), make_job(), make_cv())
    assert "Company Brief" in latex
    assert "Technical Questions" in latex
    assert "Behavioural Questions" in latex
    assert "Story Bank" in latex
    assert "Quick Reference" in latex


def test_build_prep_latex_contains_job_info() -> None:
    latex = _build_prep_latex(make_prep_data(), make_job(), make_cv())
    assert "Acme Corp" in latex
    assert "ML Engineer" in latex
    assert "Test User" in latex


def test_build_prep_latex_contains_questions() -> None:
    latex = _build_prep_latex(make_prep_data(), make_job(), make_cv())
    assert "PyTorch" in latex
    assert "class imbalance" in latex.lower()


def test_build_prep_latex_confidence_colors() -> None:
    latex = _build_prep_latex(make_prep_data(), make_job(), make_cv())
    assert "green" in latex
    assert "high" in latex


def test_build_prep_latex_story_bank() -> None:
    latex = _build_prep_latex(make_prep_data(), make_job(), make_cv())
    assert "TestVision Achievement" in latex
    assert "95\\% accuracy" in latex or "95% accuracy" in latex


def test_build_prep_latex_quick_reference() -> None:
    latex = _build_prep_latex(make_prep_data(), make_job(), make_cv())
    assert "Quick Reference" in latex
    assert "No production deployment" in latex


@pytest.mark.asyncio
async def test_generate_prep_calls_provider() -> None:
    from nj.tailoring.prep_generator import generate_prep

    mock_provider = MagicMock()
    mock_provider.name.return_value = "claude"
    mock_provider.complete = AsyncMock(
        return_value=LLMResponse(
            content=json.dumps(make_prep_data()),
            provider="claude",
            model="claude-sonnet-4-20250514",
            input_tokens=1000,
            output_tokens=500,
            latency_ms=2000,
        )
    )
    result = await generate_prep(make_job(), make_cv(), Config(), mock_provider)
    assert "technical_questions" in result
    assert "quick_reference" in result
    assert len(result["technical_questions"]) == 2


def test_run_prep_no_cv(tmp_path, monkeypatch) -> None:
    from io import StringIO

    from rich.console import Console

    from nj.cli.cmd_prep import run_prep

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_prep.console", c):
        run_prep(Config(), db_path=str(tmp_path / "nj.db"))
    assert "cv_base.json" in buf.getvalue()
