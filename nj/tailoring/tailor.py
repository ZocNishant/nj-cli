from __future__ import annotations

import copy
import json

from nj.models.config import Config
from nj.models.job import Job
from nj.models.score import ScoreResult
from nj.prompts import cover_letter_v1, tailoring_v1
from nj.providers.base import BaseLLMProvider, LLMRequest
from nj.tailoring.anti_hallucination import validate_tailored_cv
from nj.tailoring.keyword_align import extract_keywords, flatten_skills
from nj.tailoring.section_ranker import rank_projects
from nj.tailoring.suppressor import suppress_for_role
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class TailoringError(Exception):
    pass


async def tailor_cv(
    job: Job,
    score: ScoreResult,
    cv_base: dict,
    config: Config,
    provider: BaseLLMProvider,
) -> tuple[dict, str]:
    logger.info("tailoring_start", job_id=job.id, title=job.title, company=job.company)

    existing_skills = flatten_skills(cv_base.get("skills", {}))
    keywords = extract_keywords(job.description, existing_skills)

    cv_ranked = copy.deepcopy(cv_base)
    cv_ranked["projects"] = rank_projects(cv_base.get("projects", []), score)

    cv_suppressed = suppress_for_role(cv_ranked, job, score)

    tailored_cv = None
    for attempt in range(1, 3):
        try:
            user_prompt = tailoring_v1.build_user_prompt(
                job_title=job.title,
                job_company=job.company,
                job_description=job.description,
                score_result=score.model_dump(),
                cv_base=cv_suppressed,
                keywords=keywords,
            )
            request = LLMRequest(
                system=tailoring_v1.SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=3000,
                temperature=0.4,
                response_format="json",
            )
            response = await provider.complete(request)
            parsed = _parse_cv_json(response.content)
            if parsed is None:
                logger.warning("tailor_parse_failed", attempt=attempt)
                continue

            is_valid, violations = validate_tailored_cv(cv_base, parsed)
            if not is_valid:
                logger.warning(
                    "hallucination_detected_retry",
                    attempt=attempt,
                    violations=violations[:2],
                )
                if attempt < 2:
                    continue
                logger.warning("using_suppressed_cv_fallback", job_id=job.id)
                tailored_cv = cv_suppressed
                break

            tailored_cv = parsed
            logger.info(
                "tailoring_complete", job_id=job.id, keywords_injected=len(keywords)
            )
            break

        except Exception as e:
            logger.warning("tailor_attempt_failed", attempt=attempt, error=str(e))

    if tailored_cv is None:
        logger.warning("tailor_all_failed_using_base", job_id=job.id)
        tailored_cv = cv_suppressed

    cover_letter = await _generate_cover_letter(job, score, cv_base, provider)

    return tailored_cv, cover_letter


def _parse_cv_json(raw: str) -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1])
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            return None


async def _generate_cover_letter(
    job: Job,
    score: ScoreResult,
    cv_base: dict,
    provider: BaseLLMProvider,
) -> str:
    try:
        user_prompt = cover_letter_v1.build_user_prompt(
            job_title=job.title,
            job_company=job.company,
            job_description=job.description,
            matched_skills=score.matched_skills,
            overall_rationale=score.overall_rationale,
            cv_base=cv_base,
        )
        request = LLMRequest(
            system=cover_letter_v1.SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=600,
            temperature=0.5,
            response_format="text",
        )
        response = await provider.complete(request)
        return response.content
    except Exception as e:
        logger.warning("cover_letter_failed", error=str(e))
        return f"Cover letter generation failed: {e}"
