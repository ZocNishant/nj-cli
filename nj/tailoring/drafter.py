"""The drafting half of the drafter-reviewer pipeline.

Runs on the tailoring tier (Sonnet 5) because this is what a recruiter reads.
The module knows how to produce one draft and how to produce a revised draft
given review feedback; it does not know when to stop. That decision belongs to
the orchestration in `nj.tailoring.tailor`, which owns the loop and the
fallback.

Both entry points are pure request-response: no retries, no validation, no
state. A failed call raises, and the caller decides whether that is fatal.
"""

from __future__ import annotations

import json

from nj.models.job import Job
from nj.models.review import ReviewReport
from nj.models.score import ScoreResult
from nj.prompts import cover_letter_v1, tailoring_v1
from nj.providers.base import BaseLLMProvider, LLMRequest
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class DrafterError(Exception):
    pass


def _revision_directive(review: ReviewReport | None) -> str:
    """Turn a review into an instruction block appended to the user turn."""
    if review is None or review.clean:
        return ""
    feedback = review.feedback_block()
    if not feedback:
        return ""
    return (
        "\n\nREVISION REQUIRED. A reviewer audited your previous draft against "
        "the base CV and rejected these claims:\n"
        f"{feedback}\n\n"
        "Produce a corrected draft. For each item above, either restate the "
        "claim so it matches what the base CV actually says, or remove it. Do "
        "not defend the claim, do not restate it in softer words while keeping "
        "the same assertion, and do not introduce anything new while fixing it."
    )


def parse_cv_json(raw: str) -> dict | None:
    """Parse a CV JSON response, tolerating a markdown fence around it."""
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


async def draft_cv(
    job: Job,
    score: ScoreResult,
    cv_for_prompt: dict,
    provider: BaseLLMProvider,
    keywords: list[str],
    review: ReviewReport | None = None,
) -> dict:
    """Produce one tailored CV draft.

    `cv_for_prompt` is the ranked-and-suppressed CV, and it goes in the system
    turn. `review`, when given, turns this into a revision round.

    Raises DrafterError if the model returns something that is not JSON.
    """
    user_prompt = tailoring_v1.build_user_prompt(
        job_title=job.title,
        job_company=job.company,
        job_description=job.description,
        score_result=score.model_dump(),
        keywords=keywords,
    ) + _revision_directive(review)

    request = LLMRequest(
        system=tailoring_v1.build_system_prompt(cv_for_prompt),
        user=user_prompt,
        max_tokens=3000,
        temperature=0.4,
        response_format="json",
    )
    response = await provider.complete(request)
    parsed = parse_cv_json(response.content)
    if parsed is None:
        raise DrafterError("drafter returned unparseable JSON")

    logger.debug(
        "cv_drafted",
        job_id=job.id,
        revision_round=bool(review),
        model=response.model,
    )
    return parsed


async def draft_cover_letter(
    job: Job,
    score: ScoreResult,
    cv_base: dict,
    provider: BaseLLMProvider,
    review: ReviewReport | None = None,
) -> str:
    """Produce one cover letter draft."""
    user_prompt = cover_letter_v1.build_user_prompt(
        job_title=job.title,
        job_company=job.company,
        job_description=job.description,
        matched_skills=score.matched_skills,
        overall_rationale=score.overall_rationale,
    ) + _revision_directive(review)

    request = LLMRequest(
        system=cover_letter_v1.build_system_prompt(cv_base),
        user=user_prompt,
        max_tokens=600,
        temperature=0.5,
        response_format="text",
    )
    response = await provider.complete(request)
    content = response.content.strip()
    if not content:
        raise DrafterError("drafter returned an empty cover letter")

    logger.debug(
        "cover_letter_drafted",
        job_id=job.id,
        revision_round=bool(review),
        words=len(content.split()),
    )
    return content
