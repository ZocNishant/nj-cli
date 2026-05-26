from __future__ import annotations

import json

from nj.models.config import Config
from nj.models.diagnosis import DiagnosisIssue, DiagnosisResult, HealthLevel, Severity
from nj.prompts import diagnosis_v1
from nj.providers.base import BaseLLMProvider, LLMRequest
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class DiagnosticsError(Exception):
    pass


async def diagnose_cv(
    cv_base: dict,
    config: Config,
    provider: BaseLLMProvider,
    recent_scores: list[dict] | None = None,
) -> DiagnosisResult:
    logger.info("diagnosis_start", target_roles=config.search.roles)

    user_prompt = diagnosis_v1.build_user_prompt(
        cv_base=cv_base,
        target_roles=config.search.roles,
        recent_scores=recent_scores,
    )
    request = LLMRequest(
        system=diagnosis_v1.SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=2000,
        temperature=0.3,
        response_format="json",
    )

    for attempt in range(1, 3):
        try:
            response = await provider.complete(request)
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            data = json.loads(raw)
            result = _parse_diagnosis(data)
            logger.info(
                "diagnosis_complete",
                health=result.overall_health,
                issues=len(result.critical_issues),
            )
            return result
        except json.JSONDecodeError as e:
            logger.warning("diagnosis_parse_failed", attempt=attempt, error=str(e))
            if attempt == 2:
                raise DiagnosticsError(
                    f"Failed to parse diagnosis after 2 attempts: {e}"
                )
        except Exception as e:
            logger.warning("diagnosis_failed", attempt=attempt, error=str(e))
            if attempt == 2:
                raise DiagnosticsError(str(e))

    raise DiagnosticsError("Unreachable")


def _parse_diagnosis(data: dict) -> DiagnosisResult:
    issues = []
    for item in data.get("critical_issues", []):
        try:
            issues.append(
                DiagnosisIssue(
                    section=item.get("section", ""),
                    issue=item.get("issue", ""),
                    severity=Severity(item.get("severity", "medium")),
                    fix=item.get("fix", ""),
                )
            )
        except Exception:
            continue

    try:
        health = HealthLevel(data.get("overall_health", "moderate"))
    except ValueError:
        health = HealthLevel.MODERATE

    return DiagnosisResult(
        overall_health=health,
        critical_issues=sorted(
            issues,
            key=lambda i: {"high": 0, "medium": 1, "low": 2}[i.severity],
        ),
        hidden_strengths=data.get("hidden_strengths", []),
        weak_sections=data.get("weak_sections", []),
        strong_sections=data.get("strong_sections", []),
        recruiter_first_impression=data.get("recruiter_first_impression", ""),
        ats_concerns=data.get("ats_concerns", []),
        positioning_mismatch=data.get("positioning_mismatch", ""),
        score_pattern_analysis=data.get("score_pattern_analysis", ""),
        top_recommendation=data.get("top_recommendation", ""),
    )
