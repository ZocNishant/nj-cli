from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel


class GateDecision(str, Enum):
    APPROVED = "approved"
    WARNING = "warning"
    BLOCKED = "blocked"


class QualityIssue(BaseModel):
    category: str
    issue: str
    severity: str
    blocking: bool


class QualityGateResult(BaseModel):
    decision: GateDecision
    confidence: float
    issues: list[QualityIssue] = []
    warnings: list[str] = []
    blocking_reasons: list[str] = []
    recommendation: str = ""
    score_at_check: int = 0
    checked_at: datetime = None

    def model_post_init(self, __context):
        if self.checked_at is None:
            self.checked_at = datetime.now(UTC)

    @property
    def is_approved(self) -> bool:
        return self.decision != GateDecision.BLOCKED

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
