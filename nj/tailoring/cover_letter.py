from __future__ import annotations

import re
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
    content: str | None = None,
) -> str | None:
    """Write the cover letter for one job to disk and return its path.

    Returns None when no letter could be produced, and in that case writes
    nothing. An absent file is a visible, safe failure; a file containing an
    apology is neither, because everything downstream — the email notifier, the
    operator about to paste it — treats the path as a finished letter.

    `content` lets a caller save a letter that has already been drafted and
    reviewed. Without it this generates a fresh one, which is both a second
    paid call and — more to the point — a letter that never went past the
    reviewer. Callers that ran `tailor_cv` should pass its letter through.
    """
    from nj.prompts import cover_letter_v1
    from nj.providers.base import LLMRequest
    from nj.tailoring.drafter import COVER_LETTER_MAX_TOKENS

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    if content is not None and content.strip():
        return _save(job, content.strip(), output_dir)

    try:
        user_prompt = cover_letter_v1.build_user_prompt(
            job_title=job.title,
            job_company=job.company,
            job_description=job.description,
            matched_skills=score.matched_skills,
            overall_rationale=score.overall_rationale,
        )
        request = LLMRequest(
            system=cover_letter_v1.build_system_prompt(cv_base),
            user=user_prompt,
            # Sized for the letter plus a reasoning model's thinking; see the
            # headroom note in nj/providers/openai.py.
            max_tokens=COVER_LETTER_MAX_TOKENS,
            temperature=0.5,
            response_format="text",
        )
        response = await provider.complete(request)
        content = response.content.strip()
    except Exception as e:
        logger.warning("cover_letter_generation_failed", error=str(e))
        return None

    if not content:
        logger.warning("cover_letter_generation_empty", job_id=job.id)
        return None

    return _save(job, content, output_dir)


_GREETING = re.compile(r"^\s*((?:Dear|Hello|Hi)\b[^,\n]{0,60},)\s*", re.IGNORECASE)
_SIGNOFF = re.compile(
    r"\s*\b(Sincerely|Best regards|Kind regards|Regards|Best|Yours sincerely|Thank you)\s*,\s*",
    re.IGNORECASE,
)


def normalize_letter_layout(content: str) -> str:
    """Put the greeting and the sign-off on their own lines.

    The model reliably writes the right words and unreliably writes the right
    line breaks — real output ran "Dear Hiring Manager, Spotify's ML Engineer
    II role..." together on one line and closed with an inline "Sincerely,
    Nishant Joshi". Asking the prompt more firmly does not fix this every time,
    and it is pure layout, so it is done deterministically here.

    Only whitespace is rewritten. Every word the reviewer approved survives.
    """
    text = content.strip()

    greeting = _GREETING.match(text)
    if greeting:
        text = f"{greeting.group(1)}\n\n{text[greeting.end() :].lstrip()}"

    # Search from the end: "Best" and "Regards" are common mid-letter words, and
    # the closing is the last such match, never the first.
    matches = list(_SIGNOFF.finditer(text))
    if matches:
        last = matches[-1]
        body = text[: last.start()].rstrip()
        closing = last.group(1).strip().capitalize()
        name = text[last.end() :].strip()
        text = f"{body}\n\n{closing},\n{name}" if name else f"{body}\n\n{closing},"

    # Collapse runs of blank lines so paragraphs are separated by exactly one.
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _save(job: Job, content: str, output_dir: str) -> str:
    content = normalize_letter_layout(content)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
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
