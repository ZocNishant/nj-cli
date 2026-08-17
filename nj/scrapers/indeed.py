from __future__ import annotations

import random
import time
from datetime import UTC, datetime

import httpx

from nj.models.config import VisaConfig
from nj.models.job import Job
from nj.scoring.visa_filter import VisaFilter
from nj.scrapers.base import BaseScraper
from nj.utils.logger import get_logger
from nj.utils.text import clean_html, truncate

logger = get_logger(__name__)


class AdzunaScraper(BaseScraper):
    """
    Adzuna job search API scraper.
    Free tier: 1000 calls/day.
    Aggregates Indeed, Glassdoor, and 15+ other sources.
    Sign up: https://developer.adzuna.com
    Set ADZUNA_APP_ID and ADZUNA_APP_KEY in .env
    """

    BASE_URL = "https://api.adzuna.com/v1/api/jobs"
    RESULTS_PER_PAGE = 20
    MAX_PAGES = 3

    def __init__(
        self,
        app_id: str,
        app_key: str,
        visa_config: VisaConfig,
        country: str = "us",
    ):
        self.app_id = app_id
        self.app_key = app_key
        self.visa_filter = VisaFilter(visa_config)
        self.country = country

    def name(self) -> str:
        return "adzuna"

    def scrape(self, roles: list[str], location: str = "United States") -> list[Job]:
        if not self.app_id or not self.app_key:
            logger.warning(
                "adzuna_credentials_missing",
                hint="Set ADZUNA_APP_ID and ADZUNA_APP_KEY in .env",
            )
            return []

        jobs: list[Job] = []
        seen_ids: set[str] = set()

        for role in roles:
            try:
                role_jobs = self._scrape_role(role, location)
                for job in role_jobs:
                    if job.id not in seen_ids:
                        seen_ids.add(job.id)
                        jobs.append(job)
                delay = random.uniform(1.0, 2.5)
                logger.info(
                    "adzuna_role_done",
                    role=role,
                    count=len(role_jobs),
                    next_delay=round(delay, 1),
                )
                time.sleep(delay)
            except Exception as e:
                logger.warning("adzuna_role_failed", role=role, error=str(e))

        logger.info("adzuna_scrape_complete", total=len(jobs), roles=len(roles))
        return jobs

    def _scrape_role(self, role: str, location: str) -> list[Job]:
        jobs = []
        for page in range(1, self.MAX_PAGES + 1):
            try:
                page_jobs = self._fetch_page(role, location, page)
                if not page_jobs:
                    break
                jobs.extend(page_jobs)
                if len(page_jobs) < self.RESULTS_PER_PAGE:
                    break
                time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                logger.warning("adzuna_page_failed", role=role, page=page, error=str(e))
                break
        return jobs

    def _fetch_page(self, role: str, location: str, page: int) -> list[Job]:
        url = f"{self.BASE_URL}/{self.country}/search/{page}"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": role,
            "where": location,
            "results_per_page": self.RESULTS_PER_PAGE,
            "content-type": "application/json",
            "sort_by": "date",
        }
        response = httpx.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        return [j for j in (self._parse_result(r) for r in results) if j is not None]

    def _parse_result(self, result: dict) -> Job | None:
        try:
            title = result.get("title", "").strip()
            company_data = result.get("company", {})
            company = company_data.get("display_name", "Unknown")
            url = result.get("redirect_url", "")
            description_raw = result.get("description", "")
            description = clean_html(description_raw)
            description = truncate(description, 3000)
            location_data = result.get("location", {})
            location = location_data.get("display_name", "")
            salary_min = result.get("salary_min")
            salary_max = result.get("salary_max")
            salary_raw = None
            if salary_min and salary_max:
                salary_raw = f"${salary_min:,.0f} - ${salary_max:,.0f}"
            elif salary_min:
                salary_raw = f"${salary_min:,.0f}+"

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
                salary_raw=salary_raw,
                source="adzuna",
                visa_label=visa_label,
                scraped_at=datetime.now(UTC),
                description_hash=Job.generate_hash(description),
            )
        except Exception as e:
            logger.warning("adzuna_parse_failed", error=str(e))
            return None


# Keep IndeedScraper as alias for backwards compatibility
IndeedScraper = AdzunaScraper
