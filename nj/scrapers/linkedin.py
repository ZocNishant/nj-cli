from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from nj.models.config import VisaConfig
from nj.models.job import Job
from nj.scrapers.base import BaseScraper
from nj.scoring.visa_filter import VisaFilter
from nj.utils.logger import get_logger
from nj.utils.text import clean_html, truncate

logger = get_logger(__name__)


class LinkedInScraper(BaseScraper):
    BASE_SEARCH_URL = "https://www.linkedin.com/jobs/search/"
    MAX_JOBS_PER_ROLE = 25
    MAX_PAGES = 3

    def __init__(
        self,
        session_cookie: str,
        visa_config: VisaConfig,
        headless: bool = True,
        screenshot_dir: str = "logs/screenshots",
    ):
        self.session_cookie = session_cookie
        self.visa_filter = VisaFilter(visa_config)
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        Path(screenshot_dir).mkdir(parents=True, exist_ok=True)

    def name(self) -> str:
        return "linkedin"

    def scrape(self, roles: list[str], location: str = "United States") -> list[Job]:
        try:
            return asyncio.run(self._scrape_async(roles, location))
        except Exception as e:
            logger.error("linkedin_scrape_fatal", error=str(e))
            return []

    async def _scrape_async(self, roles: list[str], location: str) -> list[Job]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "playwright_not_installed",
                hint="Run: playwright install chromium",
            )
            return []

        jobs: list[Job] = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            await context.add_cookies(
                [
                    {
                        "name": "li_at",
                        "value": self.session_cookie,
                        "domain": ".linkedin.com",
                        "path": "/",
                    }
                ]
            )
            page = await context.new_page()

            for role in roles:
                try:
                    role_jobs = await self._scrape_role(page, role, location)
                    jobs.extend(role_jobs)
                    delay = random.uniform(8, 15)
                    logger.debug(
                        "linkedin_role_done",
                        role=role,
                        count=len(role_jobs),
                        next_delay=round(delay, 1),
                    )
                    await asyncio.sleep(delay)
                except Exception as e:
                    logger.warning("linkedin_role_failed", role=role, error=str(e))

            await browser.close()

        logger.debug("linkedin_scrape_complete", total=len(jobs), roles=len(roles))
        return jobs

    async def _scrape_role(self, page, role: str, location: str) -> list[Job]:
        jobs: list[Job] = []
        params = {
            "keywords": role,
            "location": location,
            "f_AL": "true",
            "sortBy": "DD",
        }
        url = f"{self.BASE_SEARCH_URL}?{urlencode(params)}"

        try:
            await page.goto(url, timeout=20000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            logger.warning("linkedin_navigation_failed", role=role, error=str(e))
            return []

        if await self._is_blocked(page):
            logger.warning("linkedin_bot_detected", role=role)
            await self._screenshot(page, "bot_detected")
            return []

        job_links = await self._collect_job_links(page)
        logger.debug("linkedin_links_found", role=role, count=len(job_links))

        for link in job_links[: self.MAX_JOBS_PER_ROLE]:
            try:
                job = await self._scrape_job_page(page, link)
                if job:
                    jobs.append(job)
                delay = random.uniform(3, 7)
                await asyncio.sleep(delay)
            except Exception as e:
                logger.warning("linkedin_job_failed", url=link, error=str(e))

        return jobs

    async def _collect_job_links(self, page) -> list[str]:
        links = []
        try:
            cards = await page.query_selector_all("a[href*='/jobs/view/']")
            seen: set[str] = set()
            for card in cards:
                href = await card.get_attribute("href")
                if href and "/jobs/view/" in href:
                    base = href.split("?")[0]
                    if base not in seen:
                        seen.add(base)
                        links.append(base)
        except Exception as e:
            logger.warning("linkedin_link_collection_failed", error=str(e))
        return links

    async def _scrape_job_page(self, page, url: str) -> Job | None:
        try:
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(2000)

            if await self._is_blocked(page):
                logger.warning("linkedin_blocked_on_job", url=url)
                await self._screenshot(page, "blocked_job")
                return None

            title = await self._get_text(
                page,
                "h1.top-card-layout__title, h1.t-24",
                fallback="Unknown Title",
            )
            company = await self._get_text(
                page,
                "a.topcard__org-name-link, .top-card-layout__card a",
                fallback="Unknown Company",
            )
            location = await self._get_text(
                page,
                ".topcard__flavor--bullet, .top-card-layout__first-subline",
                fallback="",
            )

            desc_el = await page.query_selector(
                ".description__text, .show-more-less-html__markup"
            )
            description = ""
            if desc_el:
                raw_html = await desc_el.inner_html()
                description = clean_html(raw_html)

            if not description:
                logger.debug("linkedin_empty_description", url=url)
                return None

            description = truncate(description, 3000)
            visa_label = self.visa_filter.classify(description)

            job_id = Job.generate_id(company, title, url)
            return Job(
                id=job_id,
                title=title.strip(),
                company=company.strip(),
                url=url,
                description=description,
                location=location.strip(),
                source="linkedin",
                visa_label=visa_label,
                scraped_at=datetime.now(UTC),
                description_hash=Job.generate_hash(description),
            )
        except Exception as e:
            logger.warning("linkedin_job_parse_failed", url=url, error=str(e))
            return None

    async def _get_text(self, page, selector: str, fallback: str = "") -> str:
        try:
            el = await page.query_selector(selector)
            if el:
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return fallback

    async def _is_blocked(self, page) -> bool:
        url = page.url
        blocked_signals = ["/checkpoint/", "/login", "/authwall"]
        if any(signal in url for signal in blocked_signals):
            return True
        try:
            captcha = await page.query_selector("#captcha-internal, .captcha__image")
            if captcha:
                return True
        except Exception:
            pass
        return False

    async def _screenshot(self, page, reason: str) -> None:
        try:
            ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            path = Path(self.screenshot_dir) / f"{ts}_{reason}.png"
            await page.screenshot(path=str(path))
            logger.info("screenshot_saved", path=str(path))
        except Exception as e:
            logger.warning("screenshot_failed", error=str(e))
