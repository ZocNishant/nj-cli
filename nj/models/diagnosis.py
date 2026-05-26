from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel


class HealthLevel(str, Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DiagnosisIssue(BaseModel):
    section: str
    issue: str
    severity: Severity
    fix: str


class DiagnosisResult(BaseModel):
    overall_health: HealthLevel
    critical_issues: list[DiagnosisIssue] = []
    hidden_strengths: list[str] = []
    weak_sections: list[str] = []
    strong_sections: list[str] = []
    recruiter_first_impression: str = ""
    ats_concerns: list[str] = []
    positioning_mismatch: str = ""
    score_pattern_analysis: str = ""
    top_recommendation: str = ""
    diagnosed_at: datetime = None

    def model_post_init(self, __context):
        if self.diagnosed_at is None:
            self.diagnosed_at = datetime.now(UTC)
