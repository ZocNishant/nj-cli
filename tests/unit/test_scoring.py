from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from nj.models.config import Config
from nj.models.job import Job, JobStatus, VisaLabel
from nj.models.score import ScoreCategory, ScoreResult, SubScore
from nj.providers.base import LLMResponse
from nj.scoring.scorer import _build_failed_result, _parse_response, score_job


def make_job(job_id: str = "test-id") -> Job:
    return Job(
        id=job_id,
        title="ML Engineer",
        company="TechCorp",
        url="https://example.com/job",
        description="We need PyTorch and computer vision expertise. H1B sponsorship available.",
        location="San Francisco, CA",
        source="indeed",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash="abc123",
    )


def make_cv_base() -> dict:
    return {
        "skills": {
            "ml_frameworks": ["PyTorch", "TensorFlow", "OpenCV"],
            "deep_learning": ["CNNs", "Vision Transformers"],
        },
        "projects": [
            {
                "id": "gastrovision",
                "name": "GastroVision",
                "tech": ["PyTorch", "EfficientNet"],
                "priority": 1,
                "bullets": ["Achieved 96.11% accuracy on medical image classification."],
            }
        ],
    }


def make_valid_llm_response() -> str:
    return json.dumps(
        {
            "total_score": 78,
            "confidence": 0.85,
            "sub_scores": [
                {
                    "category": "skills_match",
                    "score": 85,
                    "weight": 0.30,
                    "rationale": "Strong PyTorch match",
                    "evidence": ["PyTorch expertise"],
                },
                {
                    "category": "experience_relevance",
                    "score": 70,
                    "weight": 0.25,
                    "rationale": "GastroVision is relevant",
                    "evidence": ["computer vision"],
                },
                {
                    "category": "role_alignment",
                    "score": 75,
                    "weight": 0.20,
                    "rationale": "Good alignment",
                    "evidence": ["ML Engineer"],
                },
                {
                    "category": "sponsorship_compatibility",
                    "score": 90,
                    "weight": 0.15,
                    "rationale": "H1B sponsorship offered",
                    "evidence": ["H1B sponsorship"],
                },
                {
                    "category": "location_fit",
                    "score": 80,
                    "weight": 0.05,
                    "rationale": "USA location",
                    "evidence": ["San Francisco"],
                },
                {
                    "category": "resume_strength",
                    "score": 75,
                    "weight": 0.05,
                    "rationale": "Strong profile",
                    "evidence": [],
                },
            ],
            "matched_skills": ["PyTorch", "OpenCV"],
            "missing_skills": ["Kubernetes"],
            "recommended_emphasis": ["GastroVision project"],
            "visa_compatible": True,
            "visa_notes": "H1B sponsorship explicitly offered.",
            "overall_rationale": "Strong match on CV skills and GastroVision project.",
        }
    )


def test_parse_response_valid_json() -> None:
    raw = make_valid_llm_response()
    result = _parse_response(raw, "test-id")
    assert result is not None
    assert result.total_score > 0
    assert result.confidence == 0.85
    assert len(result.sub_scores) == 6
    assert result.visa_compatible is True
    assert "PyTorch" in result.matched_skills


def test_parse_response_strips_markdown_fences() -> None:
    raw = "```json\n" + make_valid_llm_response() + "\n```"
    result = _parse_response(raw, "test-id")
    assert result is not None
    assert result.total_score > 0


def test_parse_response_returns_none_on_invalid_json() -> None:
    result = _parse_response("this is not json at all", "test-id")
    assert result is None


def test_parse_response_ignores_unknown_categories() -> None:
    data = json.loads(make_valid_llm_response())
    data["sub_scores"].append(
        {
            "category": "unknown_category_xyz",
            "score": 50,
            "weight": 0.1,
            "rationale": "test",
            "evidence": [],
        }
    )
    result = _parse_response(json.dumps(data), "test-id")
    assert result is not None
    assert all(s.category != "unknown_category_xyz" for s in result.sub_scores)


def test_build_failed_result() -> None:
    result = _build_failed_result("job-123", "test failure")
    assert result.job_id == "job-123"
    assert result.total_score == 0
    assert result.confidence == 0.0
    assert "test failure" in result.overall_rationale


def test_compute_total_uses_weights() -> None:
    sub_scores = [
        SubScore(
            category=ScoreCategory.SKILLS_MATCH, score=80, weight=0.5, rationale="test", evidence=[]
        ),
        SubScore(
            category=ScoreCategory.ROLE_ALIGNMENT,
            score=60,
            weight=0.5,
            rationale="test",
            evidence=[],
        ),
    ]
    total = ScoreResult.compute_total(sub_scores)
    assert total == 70


@pytest.mark.asyncio
async def test_score_job_success() -> None:
    job = make_job()
    cv_base = make_cv_base()
    config = Config()
    mock_provider = MagicMock()
    mock_provider.name.return_value = "claude"
    mock_provider.complete = AsyncMock(
        return_value=LLMResponse(
            content=make_valid_llm_response(),
            provider="claude",
            model="claude-sonnet-4-20250514",
            input_tokens=500,
            output_tokens=200,
            latency_ms=1200,
        )
    )
    result = await score_job(job, cv_base, config, mock_provider, repo=None)
    assert result.total_score > 0
    assert result.provider == "claude"
    assert result.prompt_version == "scoring_v1"
    assert len(result.sub_scores) == 6


@pytest.mark.asyncio
async def test_score_job_retries_on_bad_json() -> None:
    job = make_job()
    cv_base = make_cv_base()
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
                content=make_valid_llm_response(),
                provider="claude",
                model="test",
                input_tokens=10,
                output_tokens=5,
                latency_ms=100,
            ),
        ]
    )
    result = await score_job(job, cv_base, config, mock_provider, repo=None)
    assert result.total_score > 0
    assert mock_provider.complete.call_count == 2


@pytest.mark.asyncio
async def test_score_job_returns_failed_result_on_all_attempts_failing() -> None:
    job = make_job()
    cv_base = make_cv_base()
    config = Config()
    mock_provider = MagicMock()
    mock_provider.name.return_value = "claude"
    mock_provider.complete = AsyncMock(
        return_value=LLMResponse(
            content="invalid json always",
            provider="claude",
            model="test",
            input_tokens=10,
            output_tokens=5,
            latency_ms=100,
        )
    )
    result = await score_job(job, cv_base, config, mock_provider, repo=None)
    assert result.total_score == 0
    assert result.confidence == 0.0
    assert "failed" in result.overall_rationale.lower()
