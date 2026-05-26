from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from nj.models.job import Job
from nj.models.score import ScoreResult
from nj.providers.base import BaseLLMProvider
from nj.tailoring.renderer import _safe_filename
from nj.utils.logger import get_logger

logger = get_logger(__name__)


async def generate_and_save_cover_letter(
    job: Job,
    score: ScoreResult,
    cv_base: dict,
    provider: BaseLLMProvider,
    output_dir: str,
) -> str:
    from nj.prompts import cover_letter_v1
    from nj.providers.base import LLMRequest

    Path(output_dir).mkdir(parents=True, exist_ok=True)

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
        content = response.content.strip()
    except Exception as e:
        logger.warning("cover_letter_generation_failed", error=str(e))
        content = _fallback_cover_letter(job, score)

    safe_company = _safe_filename(job.company)
    safe_title = _safe_filename(job.title)
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"nj_{safe_company}_{safe_title}_{date_str}_cover.txt"
    path = Path(output_dir) / filename
    path.write_text(content, encoding="utf-8")

    logger.info("cover_letter_saved", path=str(path), words=len(content.split()))
    return str(path)


def _fallback_cover_letter(job: Job, score: ScoreResult) -> str:
    return (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to express my interest in the {job.title} "
        f"position at {job.company}.\n\n"
        f"My background and project experience align well with "
        f"this role. I am enthusiastic about contributing to "
        f"your team.\n\n"
        f"Please find my tailored CV attached.\n\n"
        f"Best regards,\n"
        f"[Your name]"
    )
