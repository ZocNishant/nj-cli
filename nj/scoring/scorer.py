from __future__ import annotations

import json
from datetime import UTC, datetime

from nj.db.repos.score_repo import ScoreRepo
from nj.models.config import Config
from nj.models.job import Job
from nj.models.score import DEFAULT_WEIGHTS, ScoreCategory, ScoreResult, SubScore
from nj.prompts import scoring_v1
from nj.providers.base import BaseLLMProvider, LLMRequest
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class ScoringError(Exception):
    pass


def _build_failed_result(job_id: str, reason: str) -> ScoreResult:
    return ScoreResult(
        job_id=job_id,
        total_score=0,
        confidence=0.0,
        sub_scores=[],
        matched_skills=[],
        missing_skills=[],
        recommended_emphasis=[],
        visa_compatible=False,
        visa_notes="",
        overall_rationale=f"Scoring failed: {reason}",
        scored_at=datetime.now(UTC),
        provider="",
        prompt_version=scoring_v1.PROMPT_VERSION,
    )


def _parse_response(raw: str, job_id: str) -> ScoreResult | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1])
        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            return None

    try:
        sub_scores = []
        weights = {k.value: v for k, v in DEFAULT_WEIGHTS.items()}
        for s in data.get("sub_scores", []):
            category_str = s.get("category", "")
            try:
                category = ScoreCategory(category_str)
            except ValueError:
                logger.warning("unknown_score_category", category=category_str)
                continue
            sub_scores.append(
                SubScore(
                    category=category,
                    score=int(s.get("score", 0)),
                    weight=weights.get(category_str, 0.05),
                    rationale=s.get("rationale", ""),
                    evidence=s.get("evidence", []),
                )
            )

        computed_total = ScoreResult.compute_total(sub_scores)
        reported_total = int(data.get("total_score", computed_total))
        total_score = computed_total if sub_scores else reported_total

        return ScoreResult(
            job_id=job_id,
            total_score=total_score,
            confidence=float(data.get("confidence", 0.5)),
            sub_scores=sub_scores,
            matched_skills=data.get("matched_skills", []),
            missing_skills=data.get("missing_skills", []),
            recommended_emphasis=data.get("recommended_emphasis", []),
            visa_compatible=bool(data.get("visa_compatible", False)),
            visa_notes=str(data.get("visa_notes", "")),
            overall_rationale=str(data.get("overall_rationale", "")),
            scored_at=datetime.now(UTC),
            provider="",
            prompt_version=scoring_v1.PROMPT_VERSION,
        )
    except Exception as e:
        logger.warning("score_parse_failed", error=str(e))
        return None


async def score_job(
    job: Job,
    cv_base: dict,
    config: Config,
    provider: BaseLLMProvider,
    repo: ScoreRepo | None = None,
) -> ScoreResult:
    logger.info("scoring_job", job_id=job.id, title=job.title, company=job.company)

    skills = cv_base.get("skills", {})
    projects = cv_base.get("projects", [])
    top_projects = sorted(projects, key=lambda p: p.get("priority", 99))[:3]
    weights = config.scoring.weights

    user_prompt = scoring_v1.build_user_prompt(
        job_title=job.title,
        job_description=job.description,
        skills=skills,
        top_projects=top_projects,
        weights=weights,
    )

    request = LLMRequest(
        system=scoring_v1.SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=1200,
        temperature=0.2,
        response_format="json",
    )

    result = None
    for attempt in range(1, 3):
        try:
            logger.info("llm_call", attempt=attempt, job_id=job.id)
            response = await provider.complete(request)
            result = _parse_response(response.content, job.id)
            if result:
                result.provider = provider.name()
                logger.info(
                    "scoring_complete",
                    job_id=job.id,
                    score=result.total_score,
                    confidence=result.confidence,
                )
                break
            else:
                logger.warning(
                    "score_parse_failed_attempt", attempt=attempt, job_id=job.id
                )
                if attempt == 1:
                    request.user += (
                        "\n\nIMPORTANT: Return ONLY the JSON object. No other text."
                    )
        except Exception as e:
            logger.warning(
                "llm_call_failed", attempt=attempt, job_id=job.id, error=str(e)
            )

    if result is None:
        logger.error("scoring_failed_all_attempts", job_id=job.id)
        result = _build_failed_result(job.id, "LLM parse failed after 2 attempts")

    if repo:
        try:
            repo.save_score(result)
        except Exception as e:
            logger.warning("score_save_failed", job_id=job.id, error=str(e))

    return result


async def score_jobs_batch(
    jobs: list[Job],
    cv_base: dict,
    config: Config,
    provider: BaseLLMProvider,
    repo: ScoreRepo | None = None,
) -> list[ScoreResult]:
    results = []
    for job in jobs:
        result = await score_job(job, cv_base, config, provider, repo)
        results.append(result)
    return results
