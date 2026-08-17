"""Orchestration for the drafter-reviewer pipeline.

The loop is: draft, review, and if the review found anything, redraft with the
findings attached. It stops on the first draft the validator accepts, or after
`MAX_ROUNDS` attempts, whichever comes first.

The fallback has not changed and is the thing to preserve: if every round is
rejected, ship `cv_suppressed` — the deterministically ranked and suppressed
base CV, which contains no model-written prose and therefore cannot contain a
hallucination. A worse-tailored CV that is true beats a well-tailored one that
is not.

Model tiers: drafting runs on the provider the caller passes (tailoring tier,
Sonnet 5); review runs on the cheap tier (Haiku 4.5) via `review_provider`. A
caller that passes no reviewer gets the drafter's provider, which still works —
it is only more expensive.
"""

from __future__ import annotations

import copy

from nj.models.config import Config
from nj.models.job import Job
from nj.models.review import ReviewReport
from nj.models.score import ScoreResult
from nj.providers.base import BaseLLMProvider
from nj.tailoring.drafter import draft_cover_letter, draft_cv
from nj.tailoring.keyword_align import extract_keywords, flatten_skills
from nj.tailoring.reviewer import review_cover_letter, review_cv
from nj.tailoring.section_ranker import rank_projects
from nj.tailoring.suppressor import suppress_for_role
from nj.utils.logger import get_logger

logger = get_logger(__name__)

# Two drafts and two reviews per application. A third round has not, in
# practice, fixed anything the second did not — a model that reasserted a claim
# after being told it was unsupported reasserts it again.
MAX_ROUNDS = 2


class TailoringError(Exception):
    pass


async def tailor_cv(
    job: Job,
    score: ScoreResult,
    cv_base: dict,
    config: Config,
    provider: BaseLLMProvider,
    review_provider: BaseLLMProvider | None = None,
) -> tuple[dict, str]:
    """Tailor a CV and write a cover letter for one job.

    Returns (tailored_cv, cover_letter). Never raises for model failures — a
    failed run degrades to the suppressed base CV and a fallback letter.
    """
    logger.info("tailoring_start", job_id=job.id, title=job.title, company=job.company)

    reviewer = review_provider or provider

    existing_skills = flatten_skills(cv_base.get("skills", {}))
    keywords = extract_keywords(job.description, existing_skills)

    cv_ranked = copy.deepcopy(cv_base)
    cv_ranked["projects"] = rank_projects(cv_base.get("projects", []), score)
    cv_suppressed = suppress_for_role(cv_ranked, job, score)

    tailored_cv = await _draft_and_review_cv(
        job=job,
        score=score,
        cv_base=cv_base,
        cv_suppressed=cv_suppressed,
        keywords=keywords,
        provider=provider,
        reviewer=reviewer,
    )

    cover_letter = await _draft_and_review_letter(
        job=job,
        score=score,
        cv_base=cv_base,
        provider=provider,
        reviewer=reviewer,
    )

    return tailored_cv, cover_letter


async def _draft_and_review_cv(
    job: Job,
    score: ScoreResult,
    cv_base: dict,
    cv_suppressed: dict,
    keywords: list[str],
    provider: BaseLLMProvider,
    reviewer: BaseLLMProvider,
) -> dict:
    review: ReviewReport | None = None

    for attempt in range(1, MAX_ROUNDS + 1):
        try:
            draft = await draft_cv(
                job=job,
                score=score,
                cv_for_prompt=cv_suppressed,
                provider=provider,
                keywords=keywords,
                review=review,
            )
        except Exception as e:
            logger.warning("draft_attempt_failed", attempt=attempt, error=str(e))
            continue

        # Audited against the true base CV, never the suppressed copy: anything
        # suppression removed must not be able to reappear unchallenged.
        review = await review_cv(cv_base, draft, reviewer)

        if review.approved:
            if review.advisory and attempt < MAX_ROUNDS:
                # Nothing blocking, but the reviewer flagged something a set
                # comparison cannot see. Worth one more round; if that round
                # fails outright we still have this draft.
                logger.info(
                    "cv_advisory_revision",
                    attempt=attempt,
                    advisory=len(review.advisory),
                )
                revised = await _try_revision(
                    job, score, cv_suppressed, keywords, provider, reviewer, cv_base, review
                )
                if revised is not None:
                    return revised
            logger.info(
                "tailoring_complete",
                job_id=job.id,
                attempt=attempt,
                keywords_injected=len(keywords),
                advisory_remaining=len(review.advisory),
            )
            return draft

        logger.warning(
            "hallucination_detected_retry",
            attempt=attempt,
            blocking=len(review.blocking),
            violations=[r.claim for r in review.blocking[:2]],
        )

    logger.warning("tailor_all_rounds_rejected_using_base", job_id=job.id)
    return cv_suppressed


async def _try_revision(
    job: Job,
    score: ScoreResult,
    cv_suppressed: dict,
    keywords: list[str],
    provider: BaseLLMProvider,
    reviewer: BaseLLMProvider,
    cv_base: dict,
    review: ReviewReport,
) -> dict | None:
    """One extra round to clear advisory findings. Returns None if it did not help.

    Returning None rather than raising lets the caller keep the already-approved
    draft: an advisory round is an improvement attempt, not a gate.
    """
    try:
        revised = await draft_cv(
            job=job,
            score=score,
            cv_for_prompt=cv_suppressed,
            provider=provider,
            keywords=keywords,
            review=review,
        )
    except Exception as e:
        logger.warning("advisory_revision_failed", error=str(e))
        return None

    revised_review = await review_cv(cv_base, revised, reviewer)
    if not revised_review.approved:
        # The revision introduced a blocking violation. Discard it.
        logger.warning("advisory_revision_regressed", blocking=len(revised_review.blocking))
        return None
    if len(revised_review.revisions) >= len(review.revisions):
        logger.debug("advisory_revision_no_improvement")
        return None

    logger.info(
        "advisory_revision_accepted",
        before=len(review.revisions),
        after=len(revised_review.revisions),
    )
    return revised


async def _draft_and_review_letter(
    job: Job,
    score: ScoreResult,
    cv_base: dict,
    provider: BaseLLMProvider,
    reviewer: BaseLLMProvider,
) -> str:
    """Draft a cover letter, then audit it.

    Findings here are all advisory — prose has no structure to validate against
    — so a flagged letter gets exactly one revision round and then ships. The
    alternative, withholding the letter, leaves the operator with nothing.
    """
    try:
        letter = await draft_cover_letter(job, score, cv_base, provider)
    except Exception as e:
        logger.warning("cover_letter_failed", error=str(e))
        return f"Cover letter generation failed: {e}"

    try:
        review = await review_cover_letter(
            cv_base, letter, job.title, job.company, provider=reviewer
        )
    except Exception as e:
        logger.warning("cover_letter_review_failed", error=str(e))
        return letter

    if review.clean:
        return letter

    logger.info("cover_letter_revision", findings=len(review.revisions))
    try:
        return await draft_cover_letter(job, score, cv_base, provider, review=review)
    except Exception as e:
        logger.warning("cover_letter_revision_failed", error=str(e))
        return letter
