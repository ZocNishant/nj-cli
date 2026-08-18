"""Which job sources are active for this run.

This function existed twice, character-identical apart from a comment, in
`cmd_run.py` and `cmd_search.py`. A source added to one was missing from the
other until someone noticed.
"""

from __future__ import annotations

import os

from nj.models.config import Config
from nj.scrapers.base import BaseScraper


def build_scrapers(config: Config) -> list[BaseScraper]:
    """Every scraper the config enables and the environment can authenticate.

    Never returns an empty list: a run with no credentials falls back to
    RemoteOK rather than reporting zero jobs, which reads as "nothing was
    posted today" instead of "you have not set any API keys".
    """
    scrapers: list[BaseScraper] = []

    jsearch_key = os.getenv("JSEARCH_API_KEY", "")
    if jsearch_key and config.scraper.jsearch_enabled:
        from nj.scrapers.jsearch import JSearchScraper

        scrapers.append(JSearchScraper(api_key=jsearch_key, visa_config=config.visa))

    # LinkedIn is deliberately absent. `LinkedInScraper` is an inert stub that
    # returns [] (see nj/scrapers/linkedin.py), so constructing it did nothing
    # except read LINKEDIN_LI_AT out of the environment and hand a live session
    # cookie to a constructor that discards it. Reading a credential that no
    # code path can use is pure exposure, so the read is gone too.

    adzuna_id = os.getenv("ADZUNA_APP_ID", config.scraper.adzuna_app_id)
    adzuna_key = os.getenv("ADZUNA_APP_KEY", config.scraper.adzuna_app_key)
    if adzuna_id and config.scraper.adzuna_enabled:
        from nj.scrapers.indeed import AdzunaScraper

        scrapers.append(
            AdzunaScraper(
                app_id=adzuna_id,
                app_key=adzuna_key,
                visa_config=config.visa,
                country=config.scraper.adzuna_country,
            )
        )

    if config.scraper.remoteok_enabled:
        from nj.scrapers.remoteok import RemoteOKScraper

        scrapers.append(RemoteOKScraper(visa_config=config.visa))

    if config.scraper.weworkremotely_enabled:
        from nj.scrapers.weworkremotely import WeWorkRemotelyScraper

        scrapers.append(WeWorkRemotelyScraper(visa_config=config.visa))

    if config.scraper.arbeitnow_enabled:
        from nj.scrapers.arbeitnow import ArbeitnowScraper

        scrapers.append(ArbeitnowScraper(visa_config=config.visa))

    usajobs_key = os.getenv("USAJOBS_API_KEY", "")
    usajobs_agent = os.getenv("USAJOBS_USER_AGENT", "")
    if usajobs_key and usajobs_agent and config.scraper.usajobs_enabled:
        from nj.scrapers.usajobs import USAJobsScraper

        scrapers.append(
            USAJobsScraper(
                api_key=usajobs_key,
                user_agent=usajobs_agent,
                visa_config=config.visa,
            )
        )

    if not scrapers:
        from nj.scrapers.remoteok import RemoteOKScraper

        scrapers.append(RemoteOKScraper(visa_config=config.visa))

    return scrapers
