from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from nj.models.config import VisaConfig
from nj.models.job import Job
from nj.scrapers.base import BaseScraper
from nj.scoring.visa_filter import VisaFilter
from nj.utils.logger import get_logger
from nj.utils.text import clean_html, truncate

logger = get_logger(__name__)


class IndeedScraper(BaseScraper):
    BASE_URL = "https://www.indeed.com/jobs"

    def __init__(self, visa_config: VisaConfig):
        self.visa_filter = VisaFilter(visa_config)

    def name(self) -> str:
        return "indeed"

    def scrape(self, roles: list[str], location: str = "United States") -> list[Job]:
        try:
            return asyncio.run(self._scrape_async(roles, location))
        except Exception as e:
            logger.error("indeed_scrape_fatal", error=str(e))
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
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            for role in roles:
                try:
                    fetched = await self._fetch_role(page, role, location)
                    jobs.extend(fetched)
                    delay = random.uniform(2, 5)
                    logger.info(
                        "indeed_role_done",
                        role=role,
                        count=len(fetched),
                        next_delay=round(delay, 1),
                    )
                    await asyncio.sleep(delay)
                except Exception as e:
                    logger.warning("indeed_role_failed", role=role, error=str(e))

            await browser.close()

        logger.info("indeed_scrape_complete", total=len(jobs), roles=len(roles))
        return jobs

    async def _fetch_role(self, page, role: str, location: str) -> list[Job]:
        params = {"q": role, "l": location, "sort": "date", "fromage": "7"}
        url = f"{self.BASE_URL}?{urlencode(params)}"
        try:
            await page.goto(url, timeout=20000)
            try:
                await page.wait_for_selector("div.job_seen_beacon", timeout=8000)
            except Exception:
                pass
            html = await page.content()
            return self._parse_html(html)
        except Exception as e:
            logger.warning("indeed_fetch_failed", role=role, error=str(e))
            return []

    def _parse_html(self, html: str) -> list[Job]:
        jobs = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select("div.job_seen_beacon, div.jobsearch-SerpJobCard, div.result")
            if not cards:
                cards = soup.select("div[class*='job_seen'], div[class*='tapItem']")
            for card in cards:
                job = self._parse_card(card)
                if job:
                    jobs.append(job)
        except Exception as e:
            logger.warning("indeed_parse_error", error=str(e))
        return jobs

    def _parse_card(self, card) -> Job | None:
        try:
            title_el = card.select_one("h2.jobTitle a, h2 a[data-jk]")
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            url = href if href.startswith("http") else f"https://www.indeed.com{href}"

            company_el = card.select_one(
                'span[data-testid="company-name"], span.companyName, [class*="companyName"]'
            )
            company = company_el.get_text(strip=True) if company_el else "Unknown"

            location_el = card.select_one(
                'div[data-testid="text-location"], div.companyLocation, [class*="companyLocation"]'
            )
            location = location_el.get_text(strip=True) if location_el else ""

            desc_el = card.select_one(
                "div.job-snippet, div[class*='snippet'], ul.job-snippet"
            )
            description = truncate(
                clean_html(str(desc_el)) if desc_el else title, 3000
            )

            if not title or not url:
                return None

            job_id = Job.generate_id(company, title, url)
            visa_label = self.visa_filter.classify(description)
            return Job(
                id=job_id,
                title=title,
                company=company,
                url=url,
                description=description,
                location=location,
                source="indeed",
                visa_label=visa_label,
                scraped_at=datetime.now(UTC),
                description_hash=Job.generate_hash(description),
            )
        except Exception as e:
            logger.warning("indeed_card_parse_failed", error=str(e))
            return None
