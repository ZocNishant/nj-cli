from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from nj.models.job import Job


class BaseScraper(ABC):
    """A job source.

    The interface is async because every caller is: both pipelines gather all
    sources concurrently, so one slow board must not serialise the rest.

    Implementations supply `fetch`, which is ordinary blocking code — the
    boards are plain HTTP and `httpx`'s sync client is the simpler thing to
    write and test against. The base class puts it on a worker thread.

    This used to be declared `def scrape` while both call sites branched on
    `inspect.iscoroutinefunction(scraper.scrape)` and fell back to a thread.
    All eight implementations were synchronous, so the async branch was dead
    code, and a new scraper author had no contract to follow. A source that is
    genuinely async can now override `scrape` directly.
    """

    async def scrape(self, roles: list[str], location: str | None = None) -> list[Job]:
        """Every job this source has for these roles. Never raises."""
        if location is None:
            return await asyncio.to_thread(self.fetch, roles)
        return await asyncio.to_thread(self.fetch, roles, location)

    @abstractmethod
    def fetch(self, roles: list[str], location: str) -> list[Job]:
        """Blocking implementation. Never raises — handle everything internally."""
        ...

    @abstractmethod
    def name(self) -> str: ...
