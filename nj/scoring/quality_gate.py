from __future__ import annotations

import re

from nj.models.config import Config
from nj.models.job import Job
from nj.models.quality import GateDecision, QualityGateResult, QualityIssue
from nj.models.score import ScoreResult
from nj.utils.logger import get_logger

logger = get_logger(__name__)

BANNED_COVER_LETTER_PHRASES = [
    "i am passionate about",
    "i would be a great fit",
    "i am writing to apply",
    "please find attached",
    "to whom it may concern",
    "i have always been",
    "my name is",
    "i am excited to",
]

SENIOR_SIGNALS = [
    r"\b(10|8|9)\+?\s*years?\b",
    r"\bstaff\s+engineer\b",
    r"\bprincipal\s+engineer\b",
    r"\bdirector\b",
    r"\bvp\s+of\b",
    r"\blead\s+researcher\b",
]

NO_SPONSORSHIP_SIGNALS = [
    "no sponsorship",
    "citizen only",
    "green card only",
    "must be authorized",
    "no visa",
    "us citizens only",
    "permanent residents only",
]


def check_application_quality(
    job: Job,
    tailored_cv: dict,
    cover_letter: str,
    score: ScoreResult,
    config: Config,
) -> QualityGateResult:
    issues: list[QualityIssue] = []
    warnings: list[str] = []
    blocking_reasons: list[str] = []

    # 1. Score threshold check
    if score.total_score < config.scoring.threshold:
        blocking_reasons.append(
            f"Score {score.total_score} below threshold {config.scoring.threshold}"
        )
        issues.append(
            QualityIssue(
                category="score",
                issue=(
                    f"Total score {score.total_score}/100 is below "
                    f"your threshold of {config.scoring.threshold}"
                ),
                severity="high",
                blocking=True,
            )
        )

    # 2. Visa compatibility check
    if config.visa.enabled and config.visa.skip_no_sponsorship:
        jd_lower = job.description.lower()
        for signal in NO_SPONSORSHIP_SIGNALS:
            if signal in jd_lower:
                blocking_reasons.append(f"Job contains no-sponsorship signal: '{signal}'")
                issues.append(
                    QualityIssue(
                        category="visa",
                        issue=f"Job description contains '{signal}' — likely no sponsorship",
                        severity="high",
                        blocking=True,
                    )
                )
                break

    # 3. Seniority mismatch check
    jd_lower = job.description.lower()
    for pattern in SENIOR_SIGNALS:
        if re.search(pattern, jd_lower, re.IGNORECASE):
            warnings.append(f"Job may require senior-level experience (matched: '{pattern}')")
            issues.append(
                QualityIssue(
                    category="seniority",
                    issue="Job description signals senior/staff level requirement",
                    severity="medium",
                    blocking=False,
                )
            )
            break

    # 4. Cover letter quality checks
    if cover_letter:
        cover_lower = cover_letter.lower()
        for phrase in BANNED_COVER_LETTER_PHRASES:
            if phrase in cover_lower:
                warnings.append(f"Cover letter contains weak phrase: '{phrase}'")
                issues.append(
                    QualityIssue(
                        category="cover_letter",
                        issue=f"Weak phrase detected: '{phrase}'",
                        severity="low",
                        blocking=False,
                    )
                )

        word_count = len(cover_letter.split())
        if word_count > 350:
            warnings.append(f"Cover letter is {word_count} words — aim for under 300")
        elif word_count < 50:
            warnings.append(f"Cover letter is only {word_count} words — too short")

    # 5. CV completeness check
    personal = tailored_cv.get("personal", {})
    for field in ["name", "email", "phone", "linkedin"]:
        if not personal.get(field):
            warnings.append(f"CV missing personal field: {field}")

    # 6. Missing skills gap severity check
    critical_missing = [
        s
        for s in score.missing_skills
        if any(kw in s.lower() for kw in ["required", "must", "essential"])
    ]
    if critical_missing:
        warnings.append(f"Missing potentially required skills: {', '.join(critical_missing[:3])}")

    # 7. Low confidence check
    if score.confidence < 0.4:
        warnings.append(
            f"Low scoring confidence ({score.confidence:.2f}) — "
            "job description may be vague or unusual"
        )

    # Determine decision
    if blocking_reasons:
        decision = GateDecision.BLOCKED
        recommendation = f"Application blocked. Fix: {blocking_reasons[0]}"
    elif len(warnings) >= 3:
        decision = GateDecision.WARNING
        recommendation = (
            f"Proceed with caution — {len(warnings)} warnings. Review before submitting."
        )
    else:
        decision = GateDecision.APPROVED
        recommendation = "Application quality is good. Approved."

    result = QualityGateResult(
        decision=decision,
        confidence=score.confidence,
        issues=issues,
        warnings=warnings,
        blocking_reasons=blocking_reasons,
        recommendation=recommendation,
        score_at_check=score.total_score,
    )

    logger.info(
        "quality_gate_result",
        job_id=job.id,
        decision=decision,
        score=score.total_score,
        issues=len(issues),
        warnings=len(warnings),
    )
    return result
