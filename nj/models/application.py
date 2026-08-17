from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FAILED = "failed"
    CAPTCHA_BLOCKED = "captcha_blocked"
    BOT_DETECTED = "bot_detected"
    SKIPPED_THRESHOLD = "skipped_threshold"
    SKIPPED_VISA = "skipped_visa"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    REJECTED = "rejected"


class OutcomeType(str, Enum):
    INTERVIEW = "interview"
    REJECTION = "rejection"
    OFFER = "offer"
    NO_RESPONSE = "no_response"
    UNKNOWN = "unknown"


class ApplicationRecord(BaseModel):
    id: str
    job_id: str
    applied_at: datetime | None = None
    status: ApplicationStatus = ApplicationStatus.PENDING
    cv_path: str | None = None
    cover_letter_path: str | None = None
    score: int = 0
    error_message: str | None = None
    retry_count: int = 0
    screenshot_path: str | None = None
    outcome: OutcomeType | None = None
    outcome_recorded_at: datetime | None = None

    @classmethod
    def create(cls, job_id: str, score: int) -> ApplicationRecord:
        return cls(id=str(uuid.uuid4()), job_id=job_id, score=score)
