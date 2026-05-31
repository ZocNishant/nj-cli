"""
Ghost job detector.
Filters jobs before scoring to save API credits.

Ghost job signals:
- Posted >30 days ago with no updates
- Unrealistic requirements (10+ years for junior role)
- Salary wildly out of range
- No company information
- Mass repost patterns
- Generic/vague descriptions
- Missing key information
"""
from __future__ import annotations

import re
from datetime import datetime, UTC, timedelta

from nj.models.job import Job
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class GhostSignal:
    STALE = "stale_posting"
    UNREALISTIC_REQUIREMENTS = "unrealistic_requirements"
    VAGUE_DESCRIPTION = "vague_description"
    NO_COMPANY_INFO = "no_company_info"
    SPAM_PATTERN = "spam_pattern"
    SALARY_MISMATCH = "salary_mismatch"
    MASS_REPOST = "mass_repost"


class GhostJobResult:
    def __init__(
        self,
        is_ghost: bool,
        confidence: float,
        signals: list[str],
        reason: str,
    ):
        self.is_ghost = is_ghost
        self.confidence = confidence
        self.signals = signals
        self.reason = reason


SPAM_PATTERNS = [
    r"urgent\s+hiring",
    r"immediate\s+joiners?",
    r"walk.?in\s+interview",
    r"no\s+experience\s+required.*\$[5-9]\d{4}",
    r"work\s+from\s+home.*\$\d{3,4}\s+per\s+(day|hour)",
    r"make\s+\$\d+\s+(daily|per day)",
    r"be\s+your\s+own\s+boss",
    r"unlimited\s+earning",
    r"pyramid",
    r"mlm\s+",
    r"crypto.*earn",
    r"nft.*job",
]

UNREALISTIC_PATTERNS = [
    (r"(junior|entry.?level|associate).*(\d{2})\+?\s+years?", "junior_role_senior_exp"),
    (r"(react|angular|vue).*(django|rails|spring).*(ios|android).*(ml|ai|data)", "impossible_stack"),
]

VAGUE_INDICATORS = [
    "various duties",
    "other duties as assigned",
    "responsibilities may include",
    "competitive salary",
    "we are looking for a passionate",
    "rockstar developer",
    "ninja",
    "guru",
    "wizard",
]

MIN_DESCRIPTION_LENGTH = 200
MAX_REASONABLE_YEARS = 8


class GhostJobFilter:
    def __init__(
        self,
        max_age_days: int = 45,
        min_description_length: int = MIN_DESCRIPTION_LENGTH,
        enabled: bool = True,
    ):
        self.max_age_days = max_age_days
        self.min_description_length = min_description_length
        self.enabled = enabled
        self._seen_descriptions: dict[str, int] = {}

    def check(self, job: Job) -> GhostJobResult:
        if not self.enabled:
            return GhostJobResult(False, 0.0, [], "filter disabled")

        signals = []
        confidence_factors = []

        stale, stale_conf = self._check_stale(job)
        if stale:
            signals.append(GhostSignal.STALE)
            confidence_factors.append(stale_conf)

        spam, spam_conf = self._check_spam(job)
        if spam:
            signals.append(GhostSignal.SPAM_PATTERN)
            confidence_factors.append(spam_conf)

        vague, vague_conf = self._check_vague(job)
        if vague:
            signals.append(GhostSignal.VAGUE_DESCRIPTION)
            confidence_factors.append(vague_conf)

        no_company, nc_conf = self._check_no_company(job)
        if no_company:
            signals.append(GhostSignal.NO_COMPANY_INFO)
            confidence_factors.append(nc_conf)

        unrealistic, ur_conf = self._check_unrealistic(job)
        if unrealistic:
            signals.append(GhostSignal.UNREALISTIC_REQUIREMENTS)
            confidence_factors.append(ur_conf)

        repost, rp_conf = self._check_repost(job)
        if repost:
            signals.append(GhostSignal.MASS_REPOST)
            confidence_factors.append(rp_conf)

        if not signals:
            return GhostJobResult(False, 0.0, [], "clean")

        avg_conf = sum(confidence_factors) / len(confidence_factors)
        signal_boost = min(len(signals) * 0.1, 0.3)
        final_conf = min(avg_conf + signal_boost, 1.0)

        is_ghost = final_conf >= 0.6
        reason = self._build_reason(signals, job)

        logger.debug(
            "ghost_check",
            job_id=job.id,
            is_ghost=is_ghost,
            confidence=round(final_conf, 2),
            signals=signals,
        )

        return GhostJobResult(
            is_ghost=is_ghost,
            confidence=round(final_conf, 2),
            signals=signals,
            reason=reason,
        )

    def filter_jobs(
        self, jobs: list[Job]
    ) -> tuple[list[Job], list[tuple[Job, GhostJobResult]]]:
        """Returns (clean_jobs, ghost_jobs). ghost_jobs is list of (job, result) tuples."""
        clean = []
        ghosts = []
        for job in jobs:
            result = self.check(job)
            if result.is_ghost:
                ghosts.append((job, result))
            else:
                clean.append(job)

        if ghosts:
            logger.info(
                "ghost_jobs_filtered",
                total=len(jobs),
                clean=len(clean),
                ghosts=len(ghosts),
            )
        return clean, ghosts

    def _check_stale(self, job: Job) -> tuple[bool, float]:
        if not job.scraped_at:
            return False, 0.0
        try:
            scraped = job.scraped_at
            if scraped.tzinfo is None:
                scraped = scraped.replace(tzinfo=UTC)
            age_days = (datetime.now(UTC) - scraped).days
            if age_days > self.max_age_days:
                conf = min(0.5 + (age_days - self.max_age_days) / 100, 0.9)
                return True, conf
        except Exception:
            pass
        return False, 0.0

    def _check_spam(self, job: Job) -> tuple[bool, float]:
        text = (job.title + " " + job.description).lower()
        for pattern in SPAM_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True, 0.9
        return False, 0.0

    def _check_vague(self, job: Job) -> tuple[bool, float]:
        if len(job.description) < self.min_description_length:
            return True, 0.7
        desc_lower = job.description.lower()
        vague_count = sum(1 for indicator in VAGUE_INDICATORS if indicator in desc_lower)
        if vague_count >= 2:
            return True, 0.5 + vague_count * 0.05
        return False, 0.0

    def _check_no_company(self, job: Job) -> tuple[bool, float]:
        if not job.company or job.company.lower() in (
            "unknown", "confidential", "undisclosed", "n/a", ""
        ):
            return True, 0.6
        return False, 0.0

    def _check_unrealistic(self, job: Job) -> tuple[bool, float]:
        text = (job.title + " " + job.description).lower()
        for pattern, _ in UNREALISTIC_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True, 0.7
        ml_role = any(
            kw in text for kw in [
                "machine learning", "ml engineer",
                "computer vision", "ai engineer",
            ]
        )
        if ml_role:
            years_matches = re.findall(
                r"(\d+)\+?\s*years?\s*(of\s+)?experience",
                text,
            )
            for match in years_matches:
                years = int(match[0])
                if years > MAX_REASONABLE_YEARS:
                    return True, 0.6
        return False, 0.0

    def _check_repost(self, job: Job) -> tuple[bool, float]:
        fingerprint = job.description[:200].strip()
        if fingerprint in self._seen_descriptions:
            self._seen_descriptions[fingerprint] += 1
            count = self._seen_descriptions[fingerprint]
            return True, min(0.5 + count * 0.1, 0.9)
        self._seen_descriptions[fingerprint] = 1
        return False, 0.0

    def _build_reason(self, signals: list[str], job: Job) -> str:
        parts = []
        if GhostSignal.STALE in signals:
            parts.append("stale posting")
        if GhostSignal.SPAM_PATTERN in signals:
            parts.append("spam pattern detected")
        if GhostSignal.VAGUE_DESCRIPTION in signals:
            parts.append(f"description too vague ({len(job.description)} chars)")
        if GhostSignal.NO_COMPANY_INFO in signals:
            parts.append("no company information")
        if GhostSignal.UNREALISTIC_REQUIREMENTS in signals:
            parts.append("unrealistic requirements")
        if GhostSignal.MASS_REPOST in signals:
            parts.append("duplicate/repost detected")
        return "; ".join(parts)
