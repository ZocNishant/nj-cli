from __future__ import annotations

import random
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import httpx

from nj.models.config import VisaConfig
from nj.models.job import Job
from nj.scrapers.base import BaseScraper
from nj.scoring.visa_filter import VisaFilter
from nj.utils.logger import get_logger
from nj.utils.text import clean_html

logger = get_logger(__name__)


class IndeedScraper(BaseScraper):
    BASE_URL = "https://www.indeed.com/rss"

    def __init__(self, visa_config: VisaConfig):
        self.visa_filter = VisaFilter(visa_config)

    def name(self) -> str:
        return "indeed"

    def scrape(self, roles: list[str], location: str = "United States") -> list[Job]:
        jobs: list[Job] = []
        for role in roles:
            try:
                fetched = self._fetch_role(role, location)
                jobs.extend(fetched)
                delay = random.uniform(2, 5)
                logger.info(
                    "indeed_role_done",
                    role=role,
                    count=len(fetched),
                    next_delay=round(delay, 1),
                )
                time.sleep(delay)
            except Exception as e:
                logger.warning("indeed_role_failed", role=role, error=str(e))
        logger.info("indeed_scrape_complete", total=len(jobs), roles=len(roles))
        return jobs

    def _fetch_role(self, role: str, location: str) -> list[Job]:
        params = {"q": role, "l": location, "sort": "date"}
        try:
            response = httpx.get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status()
            return self._parse_rss(response.text)
        except Exception as e:
            logger.warning("indeed_fetch_failed", role=role, error=str(e))
            return []

    def _parse_rss(self, xml_text: str) -> list[Job]:
        jobs = []
        try:
            root = ET.fromstring(xml_text)
            channel = root.find("channel")
            if channel is None:
                return []
            for item in channel.findall("item"):
                job = self._parse_item(item)
                if job:
                    jobs.append(job)
        except ET.ParseError as e:
            logger.warning("indeed_parse_error", error=str(e))
        return jobs

    def _parse_item(self, item: ET.Element) -> Job | None:
        try:
            title = item.findtext("title", "").strip()
            url = item.findtext("link", "").strip()
            description_raw = item.findtext("description", "")
            description = clean_html(description_raw)
            source_elem = item.find("source")
            company = source_elem.text.strip() if source_elem is not None else "Unknown"
            location_elem = item.find("{https://www.indeed.com/about/}location")
            location = location_elem.text.strip() if location_elem is not None else ""
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
            logger.warning("indeed_item_parse_failed", error=str(e))
            return None
