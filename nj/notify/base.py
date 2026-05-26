from __future__ import annotations

from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    @abstractmethod
    def send_application_email(
        self,
        job_title: str,
        company: str,
        job_url: str,
        score: int,
        confidence: float,
        matched_skills: list[str],
        missing_skills: list[str],
        visa_label: str,
        visa_notes: str,
        cv_path: str | None,
        cover_letter_path: str | None,
    ) -> bool: ...

    @abstractmethod
    def send_daily_summary(
        self,
        applications: list[dict],
    ) -> bool: ...
