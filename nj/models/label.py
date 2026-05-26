from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class LabelValue(str, Enum):
    YES = "yes"
    NO = "no"
    MAYBE = "maybe"


class JobLabel(BaseModel):
    job_id: str
    label: LabelValue
    user_rationale: str | None = None
    labeled_at: datetime
    score_at_label_time: int = 0
