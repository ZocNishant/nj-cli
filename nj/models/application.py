from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    # A tailored CV and cover letter exist on disk and nothing has been sent.
    # This is where `nj run` leaves every application, because nj cannot submit:
    # nj.applying.linkedin_easy raises rather than auto-apply, deliberately.
    # Only a human moves a row from GENERATED to SUBMITTED, via
    # `nj status --update-id <id> --update-status submitted`.
    GENERATED = "generated"
    # Actually sent, by a human. Never written by the pipeline.
    SUBMITTED = "submitted"
    FAILED = "failed"
    CAPTCHA_BLOCKED = "captcha_blocked"
    BOT_DETECTED = "bot_detected"
    SKIPPED_THRESHOLD = "skipped_threshold"
    SKIPPED_VISA = "skipped_visa"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    REJECTED = "rejected"


# Statuses that represent real work produced for a specific job — a rendered CV
# and letter exist, whether or not a human has sent them yet. Defined once
# because several unrelated call sites need the same answer: the daily
# rate-limit budget, the status dashboard, and the shell/banner counters. A
# status added to this tuple counts against `apply.max_per_day`.
ACTIVE_APPLICATION_STATUSES = (
    ApplicationStatus.GENERATED,
    ApplicationStatus.SUBMITTED,
)


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
