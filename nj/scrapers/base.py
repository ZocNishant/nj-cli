from __future__ import annotations

from abc import ABC, abstractmethod

from nj.models.job import Job


class BaseScraper(ABC):
    @abstractmethod
    def scrape(self, roles: list[str], location: str) -> list[Job]:
        """Scrape jobs. Never raises — handle all exceptions internally."""
        ...

    @abstractmethod
    def name(self) -> str: ...
