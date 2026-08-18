# Adding a New Scraper

## Interface

All scrapers extend `BaseScraper` from `nj/scrapers/base.py`:

```python
from nj.scrapers.base import BaseScraper
from nj.models.job import Job

class MyScraper(BaseScraper):
    def name(self) -> str:
        return "mysource"   # lowercase, no spaces

    def scrape(
        self, roles: list[str], location: str
    ) -> list[Job]:
        # Never raises — catch all exceptions internally
        # Return empty list on any failure
        ...
```

## Requirements

1. **Never raise exceptions** — catch internally, log, return []
2. **Apply visa filter** — use `VisaFilter(visa_config).classify()`
3. **Generate deterministic IDs** — use `Job.generate_id()`
4. **Clean HTML** — use `nj.utils.text.clean_html()`
5. **Respect rate limits** — add delays between requests
6. **Log progress** — use `get_logger(__name__)`

## Example (minimal)

```python
import httpx
import time
from datetime import datetime, UTC
from nj.scrapers.base import BaseScraper
from nj.models.job import Job
from nj.models.config import VisaConfig
from nj.scoring.visa_filter import VisaFilter
from nj.utils.text import clean_html
from nj.utils.logger import get_logger

logger = get_logger(__name__)

class MyScraper(BaseScraper):
    def __init__(self, visa_config: VisaConfig):
        self.visa_filter = VisaFilter(visa_config)

    def name(self) -> str:
        return "mysource"

    def scrape(self, roles, location) -> list[Job]:
        jobs = []
        for role in roles:
            try:
                data = httpx.get(
                    f"https://api.example.com/jobs?q={role}",
                    timeout=15
                ).json()
                for item in data.get("results", []):
                    job = self._parse(item)
                    if job:
                        jobs.append(job)
                time.sleep(2)
            except Exception as e:
                logger.warning("scrape_failed", error=str(e))
        return jobs

    def _parse(self, item: dict) -> Job | None:
        try:
            title = item["title"]
            company = item["company"]
            url = item["url"]
            description = clean_html(item.get("description", ""))
            return Job(
                id=Job.generate_id(company, title, url),
                title=title, company=company, url=url,
                description=description, location="",
                source="mysource",
                visa_label=self.visa_filter.classify(description),
                scraped_at=datetime.now(UTC),
                description_hash=Job.generate_hash(description),
            )
        except Exception:
            return None
```

## Registering your scraper

Register it in `build_scrapers()` in `nj/pipeline/sources.py` — one place now, not two. Implement blocking `fetch()`; `BaseScraper.scrape()` is async and puts it on a worker thread.

Add a config flag to `ScraperConfig` in `nj/models/config.py`.

## Tests required

Create `tests/integration/test_scraper_mysource.py`:
- Mock HTTP calls with respx
- Add fixture JSON in `tests/fixtures/`
- Test: returns jobs, visa filter applied, empty on error,
  deterministic IDs
