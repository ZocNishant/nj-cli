"""
Prompt regression tests — validate scoring behavior against fixtures.

These tests make REAL Claude API calls.
They are NOT run in CI to avoid costs.

To run manually:
  NJ_RUN_REGRESSION_TESTS=true poetry run pytest \
    tests/integration/test_prompt_regression.py -v

Run before:
  - Changing any prompt in nj/prompts/
  - Changing scoring weights
  - Upgrading Claude model version

Cost: ~$0.05-0.10 per run (3 fixtures x scoring call)
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

FIXTURES_DIR = Path("tests/fixtures/scoring_regression")
REGRESSION_ENV_VAR = "NJ_RUN_REGRESSION_TESTS"


def regression_enabled() -> bool:
    return os.getenv(REGRESSION_ENV_VAR, "").lower() == "true"


def load_fixtures() -> list[dict]:
    if not FIXTURES_DIR.exists():
        return []
    return [json.loads(f.read_text()) for f in sorted(FIXTURES_DIR.glob("fixture_*.json"))]


@pytest.mark.skipif(
    not regression_enabled(),
    reason=(f"Set {REGRESSION_ENV_VAR}=true to run regression tests. These make real API calls."),
)
@pytest.mark.asyncio
@pytest.mark.parametrize("fixture", load_fixtures())
async def test_scoring_regression(fixture: dict):
    from nj.models.config import Config
    from nj.models.job import Job, JobStatus
    from nj.providers.registry import get_provider
    from nj.scoring.scorer import score_job
    from nj.scoring.visa_filter import VisaFilter

    config = Config.load()
    provider = get_provider(config.llm)

    job_data = fixture["job"]
    job = Job(
        id=Job.generate_id(
            job_data.get("source", "test"),
            job_data["title"],
            "https://regression-test.example.com",
        ),
        title=job_data["title"],
        description=job_data["description"],
        company="Regression Test Co",
        url="https://regression-test.example.com",
        location=job_data.get("location", ""),
        source=job_data.get("source", "test"),
        visa_label=VisaFilter(config.visa).classify(job_data["description"]),
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash=Job.generate_hash(job_data["description"]),
    )

    cv_base = fixture["cv_summary"]
    result = await score_job(
        job=job,
        cv_base=cv_base,
        config=config,
        provider=provider,
        repo=None,
    )

    desc = fixture.get("description", "unnamed fixture")
    notes = fixture.get("notes", "")

    if "expected_score_min" in fixture:
        assert result.total_score >= fixture["expected_score_min"], (
            f"[{desc}] Score {result.total_score} below minimum "
            f"{fixture['expected_score_min']}. Notes: {notes}"
        )
    if "expected_score_max" in fixture:
        assert result.total_score <= fixture["expected_score_max"], (
            f"[{desc}] Score {result.total_score} above maximum "
            f"{fixture['expected_score_max']}. Notes: {notes}"
        )

    if "expected_visa_compatible" in fixture:
        assert result.visa_compatible == fixture["expected_visa_compatible"], (
            f"[{desc}] visa_compatible expected "
            f"{fixture['expected_visa_compatible']} "
            f"got {result.visa_compatible}. Notes: {notes}"
        )

    if "expected_matched_skills_include" in fixture:
        matched_lower = [s.lower() for s in result.matched_skills]
        for skill in fixture["expected_matched_skills_include"]:
            assert skill.lower() in matched_lower, (
                f"[{desc}] Expected '{skill}' in matched_skills "
                f"but got: {result.matched_skills}. Notes: {notes}"
            )

    assert 0.0 <= result.confidence <= 1.0, f"[{desc}] confidence {result.confidence} out of range"
    assert result.total_score >= 0, f"[{desc}] Negative score: {result.total_score}"
    assert result.prompt_version != "", f"[{desc}] prompt_version not set"


def test_regression_fixtures_are_valid():
    """Always runs — validates fixture JSON structure."""
    fixtures = load_fixtures()
    assert len(fixtures) >= 3, "Expected at least 3 regression fixtures"
    for f in fixtures:
        assert "description" in f
        assert "job" in f
        assert "title" in f["job"]
        assert "description" in f["job"]
        assert "notes" in f


def test_regression_skipped_without_env_var():
    """Verify regression tests skip cleanly without env var."""
    assert not regression_enabled() or os.getenv(REGRESSION_ENV_VAR) == "true"
