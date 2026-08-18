from __future__ import annotations

import random
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import httpx

from nj.models.config import VisaConfig
from nj.models.job import Job
from nj.scoring.visa_filter import VisaFilter
from nj.scrapers.base import BaseScraper
from nj.utils.logger import get_logger
from nj.utils.text import clean_html, truncate

logger = get_logger(__name__)


class WeWorkRemotelyScraper(BaseScraper):
    """
    We Work Remotely RSS feed — no auth, strong remote ML roles.
    Free, reliable, ML-relevant categories.
    """

    FEEDS = {
        "programming": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "data_science": "https://weworkremotely.com/categories/remote-data-science-jobs.rss",
    }
    ML_KEYWORDS = {
        "machine learning",
        "ml engineer",
        "ai engineer",
        "computer vision",
        "deep learning",
        "data scientist",
        "pytorch",
        "tensorflow",
        "nlp",
        "llm",
        "neural",
    }

    def __init__(self, visa_config: VisaConfig):
        self.visa_filter = VisaFilter(visa_config)

    def name(self) -> str:
        return "weworkremotely"

    def fetch(self, roles: list[str], location: str = "") -> list[Job]:
        jobs: list[Job] = []
        seen_ids: set[str] = set()

        for category, url in self.FEEDS.items():
            try:
                feed_jobs = self._fetch_feed(url, category)
                filtered = self._filter_relevant(feed_jobs, roles)
                for job in filtered:
                    if job.id not in seen_ids:
                        seen_ids.add(job.id)
                        jobs.append(job)
                logger.debug(
                    "wwr_feed_done",
                    category=category,
                    total=len(feed_jobs),
                    relevant=len(filtered),
                )
                time.sleep(random.uniform(1.0, 2.0))
            except Exception as e:
                logger.warning("wwr_feed_failed", category=category, error=str(e))

        logger.debug("wwr_scrape_complete", total=len(jobs))
        return jobs

    def _fetch_feed(self, url: str, category: str) -> list[Job]:
        response = httpx.get(url, timeout=15)
        response.raise_for_status()
        return self._parse_rss(response.text, category)

    def _parse_rss(self, xml_text: str, category: str) -> list[Job]:
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
            logger.warning("wwr_parse_error", error=str(e))
        return jobs

    def _parse_item(self, item) -> Job | None:
        try:
            title_raw = item.findtext("title", "")
            if ": " in title_raw:
                company, title = title_raw.split(": ", 1)
            else:
                title = title_raw
                company = "Unknown"
            title = clean_html(title).strip()
            company = clean_html(company).strip()
            url = item.findtext("link", "").strip()
            description_raw = item.findtext("description", "")
            description = truncate(clean_html(description_raw), 3000)
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
                location="Remote",
                source="weworkremotely",
                visa_label=visa_label,
                scraped_at=datetime.now(UTC),
                description_hash=Job.generate_hash(description),
            )
        except Exception as e:
            logger.warning("wwr_item_failed", error=str(e))
            return None

    def _filter_relevant(self, jobs: list[Job], roles: list[str]) -> list[Job]:
        role_words = {w.lower() for r in roles for w in r.split()} | self.ML_KEYWORDS
        return [
            job
            for job in jobs
            if any(kw in (job.title + " " + job.description).lower() for kw in role_words)
        ]
