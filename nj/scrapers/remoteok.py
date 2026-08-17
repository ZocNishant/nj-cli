from __future__ import annotations

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

_ML_TAGS = {
    "machine-learning",
    "ai",
    "python",
    "computer-vision",
    "pytorch",
    "deep-learning",
    "data-science",
}

_API_TAGS = ["machine-learning", "computer-vision", "ai", "pytorch"]

_HEADERS = {"User-Agent": "nj-cli job hunter"}


class RemoteOKScraper(BaseScraper):
    BASE_URL = "https://remoteok.com/api"

    def __init__(self, visa_config: VisaConfig):
        self.visa_filter = VisaFilter(visa_config)

    def name(self) -> str:
        return "remoteok"

    def scrape(self, roles: list[str], location: str = "Remote") -> list[Job]:
        jobs: list[Job] = []
        seen_ids: set[str] = set()

        for tag in _API_TAGS:
            try:
                fetched = self._fetch_tag(tag)
                for job in fetched:
                    if job.id not in seen_ids:
                        seen_ids.add(job.id)
                        jobs.append(job)
                logger.debug("remoteok_tag_done", tag=tag, count=len(fetched))
                time.sleep(2)
            except Exception as e:
                logger.warning("remoteok_tag_failed", tag=tag, error=str(e))

        logger.debug("remoteok_scrape_complete", total=len(jobs))
        return jobs

    def _fetch_tag(self, tag: str) -> list[Job]:
        try:
            response = httpx.get(
                self.BASE_URL,
                params={"tag": tag},
                headers=_HEADERS,
                timeout=15,
                follow_redirects=True,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data)
        except Exception as e:
            logger.warning("remoteok_fetch_failed", tag=tag, error=str(e))
            return []

    def _parse_response(self, data: list) -> list[Job]:
        jobs = []
        for item in data:
            if not isinstance(item, dict) or "position" not in item:
                continue
            job = self._parse_item(item)
            if job:
                jobs.append(job)
        return jobs

    def _parse_item(self, item: dict) -> Job | None:
        try:
            tags = item.get("tags", [])
            if not set(tags) & _ML_TAGS:
                return None

            slug = item.get("slug", "")
            url = f"https://remoteok.com/remote-jobs/{slug}" if slug else ""
            title = item.get("position", "").strip()
            company = item.get("company", "Unknown").strip()
            location = item.get("location", "Remote").strip()
            raw_desc = item.get("description", title)
            description = truncate(clean_html(raw_desc), 3000)

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
                source="remoteok",
                visa_label=visa_label,
                scraped_at=datetime.now(UTC),
                description_hash=Job.generate_hash(description),
            )
        except Exception as e:
            logger.warning("remoteok_item_parse_failed", error=str(e))
            return None
