"""The adversarial half of the drafter-reviewer pipeline.

Two layers, combined into one `ReviewReport`:

1. **The validator** — `validate_tailored_cv` and `validate_completeness`,
   both set membership against the base CV, in opposite directions: the first
   rejects what the draft *added*, the second what it *lost*. Deterministic,
   cheap, and impossible to talk out of a finding. Both are BLOCKING: the draft
   does not ship while one stands.
2. **The reviewer model** — Haiku 4.5, asked to prove the draft wrong. It exists
   to catch what set comparison structurally cannot: a date widened, ownership
   upgraded from "contributed to" to "led", expertise implied without being
   named. Its findings are ADVISORY: they trigger a revision round but never on
   their own reject a draft the validator accepted.

That asymmetry is the point. Running the reviewer as a gate would let a cheap
model's false positive throw away a correct CV; running it as an advisor gets
its recall without handing it a veto. And the validator runs first, so a
reviewer that fails, times out, or returns nonsense degrades the pipeline to
exactly the guarantee the code had before this module existed — never below it.

The draft is semi-trusted input: it is model output derived from a scraped job
posting. It reaches the reviewer inside <tailored_draft> tags, in the user turn,
while the base CV sits in the system turn.
"""

from __future__ import annotations

from nj.models.review import REVIEW_SCHEMA, ReviewReport, Revision, Severity, Source
from nj.prompts import review_v1
from nj.providers.base import BaseLLMProvider, LLMRequest
from nj.tailoring.anti_hallucination import validate_tailored_cv
from nj.tailoring.completeness import validate_completeness
from nj.utils.logger import get_logger

logger = get_logger(__name__)

# Findings past this point are noise; a draft with 25 violations is being
# thrown away wholesale, not revised.
MAX_FINDINGS = 25


def _validator_revisions(cv_base: dict, draft: dict) -> list[Revision]:
    """Run both deterministic passes and lift their messages into Revisions."""
    _, invented = validate_tailored_cv(cv_base, draft)
    _, dropped = validate_completeness(cv_base, draft)

    findings = [(v, "This does not appear anywhere in the base CV.") for v in invented]
    findings += [(v, "Return this section unchanged rather than omitting it.") for v in dropped]

    return [
        Revision(
            location="",
            claim=claim,
            problem=problem,
            severity=Severity.BLOCKING,
            source=Source.VALIDATOR,
        )
        for claim, problem in findings[:MAX_FINDINGS]
    ]


def _parse_model_revisions(payload: dict) -> tuple[list[Revision], str]:
    """Lift the model's JSON into Revisions, dropping anything malformed.

    A reviewer finding with no `claim` is unactionable — the drafter would have
    nothing to correct — so it is discarded rather than passed on.
    """
    revisions: list[Revision] = []
    for item in payload.get("revisions", [])[:MAX_FINDINGS]:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim", "")).strip()
        if not claim:
            continue
        revisions.append(
            Revision(
                location=str(item.get("location", "")).strip(),
                claim=claim,
                problem=str(item.get("problem", "")).strip() or "Not supported by the base CV.",
                severity=Severity.ADVISORY,
                source=Source.REVIEWER,
            )
        )
    return revisions, str(payload.get("summary", "")).strip()


async def _ask_reviewer(
    system: str, user: str, provider: BaseLLMProvider
) -> tuple[list[Revision], str, bool]:
    """One reviewer call. Never raises — returns `ran=False` on any failure."""
    from nj.tailoring.drafter import parse_cv_json

    try:
        request = LLMRequest(
            system=system,
            user=user,
            max_tokens=1500,
            temperature=0.0,
            response_format="json",
            json_schema=REVIEW_SCHEMA,
        )
        response = await provider.complete(request)
        payload = parse_cv_json(response.content)
        if not isinstance(payload, dict):
            logger.warning("reviewer_unparseable_response")
            return [], "", False
        revisions, summary = _parse_model_revisions(payload)
        return revisions, summary, True
    except Exception as e:
        # A reviewer failure must not fail the application. The validator has
        # already run and its findings stand on their own.
        logger.warning("reviewer_call_failed", error=str(e))
        return [], "", False


async def review_cv(
    cv_base: dict,
    draft: dict,
    provider: BaseLLMProvider,
) -> ReviewReport:
    """Audit a tailored CV draft against the base CV.

    `cv_base` must be the *unmodified* base CV, not the suppressed copy handed
    to the drafter — suppression drops entries, and validating against the
    shorter version would let anything it removed be reintroduced unnoticed.
    """
    validator_findings = _validator_revisions(cv_base, draft)

    model_findings, summary, ran = await _ask_reviewer(
        review_v1.build_system_prompt(cv_base),
        review_v1.build_cv_user_prompt(
            draft,
            deterministic_findings=[r.claim for r in validator_findings],
        ),
        provider,
    )

    report = ReviewReport(
        revisions=validator_findings + model_findings,
        summary=summary,
        reviewer_ran=ran,
    )
    logger.info(
        "cv_review_complete",
        approved=report.approved,
        blocking=len(report.blocking),
        advisory=len(report.advisory),
        reviewer_ran=ran,
    )
    return report


async def review_cover_letter(
    cv_base: dict,
    draft: str,
    job_title: str,
    job_company: str,
    provider: BaseLLMProvider,
) -> ReviewReport:
    """Audit a cover letter draft.

    Prose has no structure to compare set-wise, so the validator cannot
    contribute here and every finding is advisory. The letter still gets a pass
    because it is the artefact the candidate signs.
    """
    model_findings, summary, ran = await _ask_reviewer(
        review_v1.build_system_prompt(cv_base),
        review_v1.build_letter_user_prompt(draft, job_title, job_company),
        provider,
    )

    report = ReviewReport(revisions=model_findings, summary=summary, reviewer_ran=ran)
    logger.info(
        "cover_letter_review_complete",
        findings=len(report.revisions),
        reviewer_ran=ran,
    )
    return report
