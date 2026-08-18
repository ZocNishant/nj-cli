"""LinkedIn scraping — disabled by default.

This module used to drive a headless Chromium session authenticated with the
operator's own `li_at` cookie. That is the account they job-hunt from, and
LinkedIn treats automated navigation of `/jobs/search/` as bot activity: the
observable outcomes are a checkpoint challenge, a temporary restriction, or a
permanent ban on the account. Losing that account costs more than the postings
the scraper returned, and it violates LinkedIn's User Agreement either way.

So the scraper is stubbed. `scrape()` keeps the `BaseScraper` contract and
returns an empty list, which every caller already handles — `_get_enabled_scrapers`
merely contributes nothing from this source. US postings come from Adzuna and
JSearch instead (see CLAUDE.md, "Job sourcing needs US credentials").

Re-enabling this is a deliberate act, not a config flip: set
`NJ_ENABLE_LINKEDIN_SCRAPER=1` *and* restore an implementation. The env var on
its own does nothing, by design — it exists so that a future implementation has
an opt-in gate to hang off, not so that a stray value silently resurrects
account-risking behaviour.
"""

from __future__ import annotations

import os

from nj.models.config import VisaConfig
from nj.models.job import Job
from nj.scrapers.base import BaseScraper
from nj.utils.logger import get_logger

logger = get_logger(__name__)

ENABLE_ENV_VAR = "NJ_ENABLE_LINKEDIN_SCRAPER"

DISABLED_REASON = (
    "LinkedIn scraping is disabled: cookie-authenticated browser automation "
    "risks a checkpoint challenge or a permanent ban on the operator's primary "
    "account. Use Adzuna or JSearch for US postings."
)


def is_enabled() -> bool:
    """True only when the operator has explicitly opted in.

    Even then `scrape()` returns nothing, because no implementation is present.
    """
    return os.getenv(ENABLE_ENV_VAR, "").strip().lower() in {"1", "true", "yes"}


class LinkedInScraper(BaseScraper):
    """Inert stand-in for the removed Playwright scraper.

    The constructor still accepts `session_cookie` so existing call sites keep
    working, but the value is dropped on the floor rather than stored — nothing
    here can leak it into a log, a screenshot, or a browser context.
    """

    def __init__(
        self,
        session_cookie: str = "",
        visa_config: VisaConfig | None = None,
        headless: bool = True,
        screenshot_dir: str = "logs/screenshots",
    ):
        del session_cookie  # never retained: see module docstring
        self.visa_config = visa_config or VisaConfig()
        self.headless = headless
        self.screenshot_dir = screenshot_dir

    def name(self) -> str:
        return "linkedin"

    def scrape(self, roles: list[str], location: str = "United States") -> list[Job]:
        logger.warning(
            "linkedin_scraper_disabled",
            reason=DISABLED_REASON,
            opt_in_var=ENABLE_ENV_VAR,
            opted_in=is_enabled(),
            roles=len(roles),
            location=location,
        )
        return []
