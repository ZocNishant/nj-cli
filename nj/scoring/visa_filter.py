from __future__ import annotations

from nj.models.config import VisaConfig
from nj.models.job import Job, VisaLabel
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class VisaFilter:
    def __init__(self, config: VisaConfig):
        self.config = config

    def classify(self, description: str) -> VisaLabel:
        if not self.config.enabled:
            return VisaLabel.UNKNOWN
        text = description.lower()
        for kw in self.config.exclude_keywords:
            if kw.lower() in text:
                return VisaLabel.BLOCKED
        for kw in self.config.include_keywords:
            if kw.lower() in text:
                return VisaLabel.CONFIRMED
        if any(w in text for w in ["international", "global candidates", "worldwide"]):
            return VisaLabel.LIKELY
        return VisaLabel.UNKNOWN

    def should_skip(self, job: Job) -> bool:
        if not self.config.enabled:
            return False
        if not self.config.skip_no_sponsorship:
            return False
        skip = job.visa_label == VisaLabel.BLOCKED
        if skip:
            logger.info(
                "visa_blocked",
                job_id=job.id,
                company=job.company,
                title=job.title,
            )
        return skip
