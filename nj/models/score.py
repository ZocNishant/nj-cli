from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, field_validator


class ScoreCategory(str, Enum):
    SKILLS_MATCH = "skills_match"
    EXPERIENCE_RELEVANCE = "experience_relevance"
    SPONSORSHIP_COMPAT = "sponsorship_compatibility"
    LOCATION_FIT = "location_fit"
    RESUME_STRENGTH = "resume_strength"
    ROLE_ALIGNMENT = "role_alignment"


DEFAULT_WEIGHTS: dict[ScoreCategory, float] = {
    ScoreCategory.SKILLS_MATCH: 0.30,
    ScoreCategory.EXPERIENCE_RELEVANCE: 0.25,
    ScoreCategory.ROLE_ALIGNMENT: 0.20,
    ScoreCategory.SPONSORSHIP_COMPAT: 0.15,
    ScoreCategory.LOCATION_FIT: 0.05,
    ScoreCategory.RESUME_STRENGTH: 0.05,
}


class SubScore(BaseModel):
    category: ScoreCategory
    score: int
    weight: float
    rationale: str
    evidence: list[str] = []

    @field_validator("score")
    @classmethod
    def score_range(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("score must be 0-100")
        return v


class ScoreResult(BaseModel):
    job_id: str
    total_score: int
    confidence: float
    sub_scores: list[SubScore] = []
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    recommended_emphasis: list[str] = []
    visa_compatible: bool = False
    visa_notes: str = ""
    overall_rationale: str = ""
    scored_at: datetime
    provider: str = ""
    prompt_version: str = ""
    raw_response: str | None = None

    @classmethod
    def compute_total(cls, sub_scores: list[SubScore]) -> int:
        if not sub_scores:
            return 0
        total = sum(s.score * s.weight for s in sub_scores)
        return round(total)
