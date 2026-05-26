from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class VisaLabel(str, Enum):
    CONFIRMED = "confirmed"
    LIKELY = "likely"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"


class JobStatus(str, Enum):
    NEW = "new"
    SCORED = "scored"
    TAILORED = "tailored"
    PENDING_REVIEW = "pending_review"
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class Job(BaseModel):
    id: str
    title: str
    company: str
    url: str
    description: str
    location: str
    salary_raw: str | None = None
    source: str
    visa_label: VisaLabel = VisaLabel.UNKNOWN
    scraped_at: datetime
    status: JobStatus = JobStatus.NEW
    description_hash: str

    @classmethod
    def generate_id(cls, company: str, title: str, url: str) -> str:
        raw = f"{company.lower().strip()}{title.lower().strip()}{url.strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def generate_hash(cls, description: str) -> str:
        return hashlib.sha256(description.encode()).hexdigest()
