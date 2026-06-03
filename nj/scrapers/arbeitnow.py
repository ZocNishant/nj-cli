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


class ArbeitnowScraper(BaseScraper):
    """
    Arbeitnow free job board API — no auth, no rate limits.
    Strong for remote + European tech roles.
    API docs: https://www.arbeitnow.com/api
    """

    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(self, visa_config: VisaConfig):
        self.visa_filter = VisaFilter(visa_config)

    def name(self) -> str:
        return "arbeitnow"

    def scrape(self, roles: list[str], location: str = "") -> list[Job]:
        jobs: list[Job] = []
        seen_ids: set[str] = set()

        tags = self._roles_to_tags(roles)

        for tag in tags:
            try:
                tag_jobs = self._fetch_tag(tag)
                for job in tag_jobs:
                    if job.id not in seen_ids:
                        seen_ids.add(job.id)
                        jobs.append(job)
                delay = random.uniform(1.0, 2.0)
                logger.debug("arbeitnow_tag_done", tag=tag, count=len(tag_jobs))
                time.sleep(delay)
            except Exception as e:
                logger.warning("arbeitnow_tag_failed", tag=tag, error=str(e))

        logger.debug("arbeitnow_scrape_complete", total=len(jobs))
        return jobs

    def _roles_to_tags(self, roles: list[str]) -> list[str]:
        tags: set[str] = set()
        role_lower = " ".join(roles).lower()
        if any(w in role_lower for w in ["ml", "machine learning", "ai"]):
            tags.add("machine-learning")
            tags.add("artificial-intelligence")
        if any(w in role_lower for w in ["python", "pytorch", "tensorflow"]):
            tags.add("python")
        if "computer vision" in role_lower:
            tags.add("computer-vision")
        if "data" in role_lower:
            tags.add("data-science")
        if not tags:
            tags.add("machine-learning")
            tags.add("python")
        return list(tags)

    def _fetch_tag(self, tag: str) -> list[Job]:
        jobs = []
        for page in range(1, 4):
            try:
                params = {"tags[]": tag, "page": page}
                response = httpx.get(self.BASE_URL, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                results = data.get("data", [])
                if not results:
                    break
                page_jobs = [
                    j for j in (self._parse(r) for r in results) if j is not None
                ]
                jobs.extend(page_jobs)
                if not data.get("links", {}).get("next"):
                    break
            except Exception as e:
                logger.warning("arbeitnow_page_failed", error=str(e))
                break
        return jobs

    def _parse(self, item: dict) -> Job | None:
        try:
            title = item.get("title", "").strip()
            company = item.get("company_name", "Unknown").strip()
            url = item.get("url", "")
            description = truncate(clean_html(item.get("description", "")), 3000)
            location = item.get("location", "Remote")
            if item.get("remote", False):
                location = "Remote"
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
                source="arbeitnow",
                visa_label=visa_label,
                scraped_at=datetime.now(UTC),
                description_hash=Job.generate_hash(description),
            )
        except Exception as e:
            logger.warning("arbeitnow_parse_failed", error=str(e))
            return None
