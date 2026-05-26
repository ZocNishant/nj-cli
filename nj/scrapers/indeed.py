from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from pathlib import Path
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
            response = await page.goto(url, timeout=20000)
            try:
                await page.wait_for_selector("div.job_seen_beacon", timeout=8000)
            except Exception:
                pass
            html = await page.content()
            logger.debug(
                "indeed_response",
                status=response.status if response else "unknown",
                html_length=len(html),
                url=str(page.url),
            )
            return self._parse_html(html)
        except Exception as e:
            logger.warning("indeed_fetch_failed", role=role, error=str(e))
            return []

    def _parse_html(self, html: str) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")

        cards = []
        for sel in [
            "div.job_seen_beacon",
            "div.tapItem",
            "div[class*='job_seen']",
            "div[class*='jobsearch-ResultsList'] > div",
            "li[class*='job']",
            "div[data-jk]",
            "td.resultContent",
        ]:
            cards = soup.select(sel)
            if cards:
                logger.debug("indeed_cards_found", selector=sel, count=len(cards))
                break

        if not cards:
            debug_path = Path("logs/indeed_debug.html")
            debug_path.parent.mkdir(exist_ok=True)
            debug_path.write_text(html[:50000])
            logger.warning(
                "indeed_no_cards_found",
                debug_saved=str(debug_path),
                html_length=len(html),
            )

        jobs = []
        for card in cards:
            job = self._parse_card(card)
            if job:
                jobs.append(job)
        return jobs

    def _parse_card(self, card) -> Job | None:
        try:
            title = ""
            for sel in [
                "h2.jobTitle a",
                "h2 a[data-jk]",
                "h2 span[title]",
                "a.jcs-JobTitle",
                "[class*='jobTitle'] a",
                "[class*='JobTitle'] a",
            ]:
                el = card.select_one(sel)
                if el:
                    title = el.get_text(strip=True)
                    break

            if not title:
                title = card.get_text(strip=True)[:80]

            url = ""
            for sel in ["h2 a", "a[data-jk]", "a[id*='job']"]:
                el = card.select_one(sel)
                if el and el.get("href"):
                    href = el["href"]
                    url = f"https://www.indeed.com{href}" if href.startswith("/") else href
                    break

            if not url:
                return None

            company = "Unknown"
            for sel in [
                "span[data-testid='company-name']",
                "[class*='companyName']",
                "[class*='company_name']",
                "span.companyName",
                "[class*='CompanyName']",
            ]:
                el = card.select_one(sel)
                if el:
                    company = el.get_text(strip=True)
                    break

            location = ""
            for sel in [
                "div[data-testid='text-location']",
                "[class*='companyLocation']",
                "[class*='location']",
            ]:
                el = card.select_one(sel)
                if el:
                    location = el.get_text(strip=True)
                    break

            description = ""
            for sel in [
                "div[class*='snippet']",
                "div[class*='Snippet']",
                "div.job-snippet",
                "ul[class*='snippet'] li",
            ]:
                els = card.select(sel)
                if els:
                    description = " ".join(e.get_text(strip=True) for e in els)
                    break

            if not description:
                description = card.get_text(separator=" ", strip=True)[:500]

            if not title or not url:
                return None

            description = truncate(clean_html(description), 3000)
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
