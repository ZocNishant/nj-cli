from __future__ import annotations

import re

from nj.models.config import Config
from nj.models.job import Job, VisaLabel
from nj.models.quality import GateDecision, QualityGateResult, QualityIssue
from nj.models.score import ScoreResult
from nj.scoring.visa_filter import VisaFilter
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

# There is no second list of sponsorship phrases here on purpose.
#
# There used to be, and it contained "must be authorized" — the exact phrase
# nj/scoring/visa_filter.py removed, with a comment explaining why: nearly every
# US posting contains it, and someone on OPT *is* authorized. So the bug was
# fixed in one classifier and left standing in the other, and this copy was the
# worse of the two: bare substring matching, no negation awareness, no phrase
# context, and it blocked.
#
# The cost was not only a wrong verdict. This gate runs *after* tailoring and
# rendering, so a false block threw away two LLM calls, a reviewer pass and a
# tectonic compile, and recorded the job as FAILED.
#
# One classifier, one place to fix it. See _visa_block_reason below.


def _visa_block_reason(job: Job, config: Config) -> str | None:
    """The evidence for blocking on sponsorship, or None to let it through.

    Re-derives from the posting rather than reading `job.visa_label`, because
    the stored label was written at scrape time and this gate exists to catch
    what the earlier stages missed. Same classifier, so the two can never
    disagree — which is the whole point of routing through it.
    """
    if not (config.visa.enabled and config.visa.skip_no_sponsorship):
        return None

    label, evidence = VisaFilter(config.visa).explain(job.description)
    if label is VisaLabel.BLOCKED:
        return evidence
    return None


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

    # 2. Visa compatibility check — delegated to the one classifier
    visa_evidence = _visa_block_reason(job, config)
    if visa_evidence:
        blocking_reasons.append(f"No-sponsorship language in the posting: {visa_evidence}")
        issues.append(
            QualityIssue(
                category="visa",
                issue=f"Posting rules out sponsorship — {visa_evidence}",
                severity="high",
                blocking=True,
            )
        )

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
