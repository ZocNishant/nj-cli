from __future__ import annotations

import random
import time
from datetime import UTC, datetime

import httpx

from nj.models.config import VisaConfig
from nj.models.job import Job
from nj.scrapers.base import BaseScraper
from nj.scoring.visa_filter import VisaFilter
from nj.utils.logger import get_logger
from nj.utils.text import clean_html, truncate

logger = get_logger(__name__)


class JSearchScraper(BaseScraper):
    """
    JSearch API — aggregates 30+ job boards via RapidAPI.
    Covers LinkedIn, Indeed, Glassdoor, ZipRecruiter, Monster,
    Dice, SimplyHired, Greenhouse, Lever, Workday and more.
    Free tier: 10 searches/day on RapidAPI.
    Sign up: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
    Set JSEARCH_API_KEY in .env
    """

    BASE_URL = "https://jsearch.p.rapidapi.com/search"
    HEADERS = {
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }

    def __init__(self, api_key: str, visa_config: VisaConfig):
        self.api_key = api_key
        self.visa_filter = VisaFilter(visa_config)

    def name(self) -> str:
        return "jsearch"

    def scrape(self, roles: list[str], location: str = "United States") -> list[Job]:
        if not self.api_key:
            logger.warning(
                "jsearch_key_missing",
                hint="Set JSEARCH_API_KEY in .env — get free key at rapidapi.com",
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
                delay = random.uniform(1.5, 3.0)
                logger.info(
                    "jsearch_role_done",
                    role=role,
                    count=len(role_jobs),
                    next_delay=round(delay, 1),
                )
                time.sleep(delay)
            except Exception as e:
                logger.warning("jsearch_role_failed", role=role, error=str(e))

        logger.info("jsearch_scrape_complete", total=len(jobs), roles=len(roles))
        return jobs

    def _scrape_role(self, role: str, location: str) -> list[Job]:
        jobs = []
        for page in range(1, 4):
            try:
                params = {
                    "query": f"{role} {location}",
                    "page": str(page),
                    "num_pages": "1",
                    "date_posted": "week",
                    "remote_jobs_only": "false",
                    "employment_types": "FULLTIME",
                }
                headers = {
                    **self.HEADERS,
                    "X-RapidAPI-Key": self.api_key,
                }
                response = httpx.get(
                    self.BASE_URL, params=params, headers=headers, timeout=15
                )
                response.raise_for_status()
                data = response.json()
                results = data.get("data", [])
                if not results:
                    break
                page_jobs = [
                    j for j in (self._parse_result(r) for r in results) if j is not None
                ]
                jobs.extend(page_jobs)
                if len(results) < 10:
                    break
                time.sleep(random.uniform(0.5, 1.0))
            except Exception as e:
                logger.warning("jsearch_page_failed", page=page, error=str(e))
                break
        return jobs

    def _parse_result(self, result: dict) -> Job | None:
        try:
            title = result.get("job_title", "").strip()
            company = result.get("employer_name", "Unknown").strip()
            url = result.get("job_apply_link", "") or result.get("job_google_link", "")
            description = truncate(clean_html(result.get("job_description", "")), 3000)

            city = result.get("job_city", "")
            state = result.get("job_state", "")
            country = result.get("job_country", "")
            location_parts = [p for p in [city, state, country] if p]
            location = ", ".join(location_parts)

            if result.get("job_is_remote", False):
                location = "Remote" + (f" ({location})" if location else "")

            salary_min = result.get("job_min_salary")
            salary_max = result.get("job_max_salary")
            salary_raw = None
            if salary_min and salary_max:
                salary_raw = f"${salary_min:,.0f} - ${salary_max:,.0f}"
            elif salary_min:
                salary_raw = f"${salary_min:,.0f}+"

            if not title or not url:
                return None

            publisher = result.get("job_publisher", "jsearch").lower()
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
                source=f"jsearch:{publisher}",
                visa_label=visa_label,
                scraped_at=datetime.now(UTC),
                description_hash=Job.generate_hash(description),
            )
        except Exception as e:
            logger.warning("jsearch_parse_failed", error=str(e))
            return None
