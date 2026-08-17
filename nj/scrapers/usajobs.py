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


class USAJobsScraper(BaseScraper):
    """
    USAJobs.gov REST API — federal government ML/AI positions.
    Requires free registration at usajobs.gov/Help/authentication/
    Set USAJOBS_API_KEY and USAJOBS_USER_AGENT in .env
    API docs: https://developer.usajobs.gov/
    """

    BASE_URL = "https://data.usajobs.gov/api/search"

    def __init__(self, api_key: str, user_agent: str, visa_config: VisaConfig):
        self.api_key = api_key
        self.user_agent = user_agent
        self.visa_filter = VisaFilter(visa_config)

    def name(self) -> str:
        return "usajobs"

    def scrape(self, roles: list[str], location: str = "") -> list[Job]:
        if not self.api_key or not self.user_agent:
            logger.warning(
                "usajobs_creds_missing",
                hint="Set USAJOBS_API_KEY and USAJOBS_USER_AGENT in .env",
            )
            return []

        jobs: list[Job] = []
        seen_ids: set[str] = set()

        for role in roles:
            try:
                role_jobs = self._scrape_role(role)
                for job in role_jobs:
                    if job.id not in seen_ids:
                        seen_ids.add(job.id)
                        jobs.append(job)
                delay = random.uniform(1.0, 2.0)
                logger.info("usajobs_role_done", role=role, count=len(role_jobs))
                time.sleep(delay)
            except Exception as e:
                logger.warning("usajobs_role_failed", role=role, error=str(e))

        logger.info("usajobs_scrape_complete", total=len(jobs))
        return jobs

    def _scrape_role(self, role: str) -> list[Job]:
        jobs = []
        for page in range(1, 4):
            try:
                params = {
                    "Keyword": role,
                    "ResultsPerPage": "25",
                    "Page": str(page),
                    "Fields": "Min",
                }
                headers = {
                    "Authorization-Key": self.api_key,
                    "User-Agent": self.user_agent,
                    "Host": "data.usajobs.gov",
                }
                response = httpx.get(self.BASE_URL, params=params, headers=headers, timeout=15)
                response.raise_for_status()
                data = response.json()
                results = data.get("SearchResult", {}).get("SearchResultItems", [])
                if not results:
                    break
                page_jobs = [j for j in (self._parse(r) for r in results) if j is not None]
                jobs.extend(page_jobs)
                total = int(data.get("SearchResult", {}).get("SearchResultCountAll", 0))
                if len(jobs) >= total or len(results) < 25:
                    break
                time.sleep(random.uniform(0.5, 1.0))
            except Exception as e:
                logger.warning("usajobs_page_failed", page=page, error=str(e))
                break
        return jobs

    def _parse(self, item: dict) -> Job | None:
        try:
            descriptor = item.get("MatchedObjectDescriptor", {})
            title = descriptor.get("PositionTitle", "").strip()
            company = descriptor.get("OrganizationName", "Unknown").strip()
            url = descriptor.get("PositionURI", "").strip()
            description = truncate(clean_html(descriptor.get("QualificationSummary", "")), 3000)

            locations = descriptor.get("PositionLocation", [])
            if locations:
                loc = locations[0]
                city = loc.get("CityName", "")
                state = loc.get("CountrySubDivisionCode", "")
                location = f"{city}, {state}".strip(", ") if city or state else "USA"
            else:
                location = "USA"

            salary_min = descriptor.get("PositionRemuneration", [{}])[0].get("MinimumRange", "")
            salary_max = descriptor.get("PositionRemuneration", [{}])[0].get("MaximumRange", "")
            salary_raw = None
            if salary_min and salary_max:
                try:
                    salary_raw = f"${float(salary_min):,.0f} - ${float(salary_max):,.0f}"
                except (ValueError, TypeError):
                    pass

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
                source="usajobs",
                visa_label=visa_label,
                scraped_at=datetime.now(UTC),
                description_hash=Job.generate_hash(description),
            )
        except Exception as e:
            logger.warning("usajobs_parse_failed", error=str(e))
            return None
