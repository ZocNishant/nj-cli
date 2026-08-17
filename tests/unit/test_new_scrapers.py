from __future__ import annotations

import xml.etree.ElementTree as ET
from unittest.mock import patch

import respx
from httpx import Response

from nj.models.config import VisaConfig

VISA_CONFIG = VisaConfig()


# ── JSearch ──────────────────────────────────────────────────────────────────


class TestJSearchScraper:
    def _make_result(self, **kwargs) -> dict:
        base = {
            "job_title": "ML Engineer",
            "employer_name": "Acme Corp",
            "job_apply_link": "https://jobs.example.com/1",
            "job_description": "Work on PyTorch models.",
            "job_city": "San Francisco",
            "job_state": "CA",
            "job_country": "US",
            "job_is_remote": False,
            "job_publisher": "linkedin",
            "job_min_salary": None,
            "job_max_salary": None,
        }
        base.update(kwargs)
        return base

    def test_empty_key_returns_no_jobs(self):
        from nj.scrapers.jsearch import JSearchScraper

        scraper = JSearchScraper(api_key="", visa_config=VISA_CONFIG)
        jobs = scraper.scrape(["ML Engineer"])
        assert jobs == []

    @respx.mock
    def test_scrape_returns_jobs(self):
        from nj.scrapers.jsearch import JSearchScraper

        payload = {"data": [self._make_result()]}
        respx.get("https://jsearch.p.rapidapi.com/search").mock(
            return_value=Response(200, json=payload)
        )
        scraper = JSearchScraper(api_key="test-key", visa_config=VISA_CONFIG)
        with patch("time.sleep"):
            jobs = scraper.scrape(["ML Engineer"])
        assert len(jobs) >= 1
        assert jobs[0].title == "ML Engineer"
        assert jobs[0].company == "Acme Corp"
        assert "jsearch" in jobs[0].source

    @respx.mock
    def test_remote_job_location(self):
        from nj.scrapers.jsearch import JSearchScraper

        result = self._make_result(
            job_is_remote=True, job_city="Austin", job_state="TX", job_country="US"
        )
        payload = {"data": [result]}
        respx.get("https://jsearch.p.rapidapi.com/search").mock(
            return_value=Response(200, json=payload)
        )
        scraper = JSearchScraper(api_key="test-key", visa_config=VISA_CONFIG)
        with patch("time.sleep"):
            jobs = scraper.scrape(["ML Engineer"])
        assert "Remote" in jobs[0].location

    @respx.mock
    def test_salary_formatted(self):
        from nj.scrapers.jsearch import JSearchScraper

        result = self._make_result(job_min_salary=120000, job_max_salary=160000)
        payload = {"data": [result]}
        respx.get("https://jsearch.p.rapidapi.com/search").mock(
            return_value=Response(200, json=payload)
        )
        scraper = JSearchScraper(api_key="test-key", visa_config=VISA_CONFIG)
        with patch("time.sleep"):
            jobs = scraper.scrape(["ML Engineer"])
        assert jobs[0].salary_raw is not None
        assert "$120,000" in jobs[0].salary_raw

    @respx.mock
    def test_missing_title_skipped(self):
        from nj.scrapers.jsearch import JSearchScraper

        result = self._make_result(job_title="")
        payload = {"data": [result]}
        respx.get("https://jsearch.p.rapidapi.com/search").mock(
            return_value=Response(200, json=payload)
        )
        scraper = JSearchScraper(api_key="test-key", visa_config=VISA_CONFIG)
        with patch("time.sleep"):
            jobs = scraper.scrape(["ML Engineer"])
        assert jobs == []


# ── Arbeitnow ─────────────────────────────────────────────────────────────────


class TestArbeitnowScraper:
    def _make_item(self, **kwargs) -> dict:
        base = {
            "title": "Data Scientist",
            "company_name": "DataCo",
            "url": "https://arbeitnow.com/jobs/1",
            "description": "<p>Work with Python and ML.</p>",
            "location": "Berlin, Germany",
            "remote": False,
        }
        base.update(kwargs)
        return base

    @respx.mock
    def test_scrape_returns_jobs(self):
        from nj.scrapers.arbeitnow import ArbeitnowScraper

        payload = {"data": [self._make_item()], "links": {}}
        respx.get("https://www.arbeitnow.com/api/job-board-api").mock(
            return_value=Response(200, json=payload)
        )
        scraper = ArbeitnowScraper(visa_config=VISA_CONFIG)
        with patch("time.sleep"):
            jobs = scraper.scrape(["ML Engineer"])
        assert len(jobs) >= 1
        assert jobs[0].source == "arbeitnow"

    @respx.mock
    def test_remote_flag_overrides_location(self):
        from nj.scrapers.arbeitnow import ArbeitnowScraper

        item = self._make_item(remote=True, location="Berlin")
        payload = {"data": [item], "links": {}}
        respx.get("https://www.arbeitnow.com/api/job-board-api").mock(
            return_value=Response(200, json=payload)
        )
        scraper = ArbeitnowScraper(visa_config=VISA_CONFIG)
        with patch("time.sleep"):
            jobs = scraper.scrape(["ML Engineer"])
        assert jobs[0].location == "Remote"

    def test_roles_to_tags_ml(self):
        from nj.scrapers.arbeitnow import ArbeitnowScraper

        scraper = ArbeitnowScraper(visa_config=VISA_CONFIG)
        tags = scraper._roles_to_tags(["ML Engineer", "AI Researcher"])
        assert "machine-learning" in tags
        assert "artificial-intelligence" in tags

    def test_roles_to_tags_default(self):
        from nj.scrapers.arbeitnow import ArbeitnowScraper

        scraper = ArbeitnowScraper(visa_config=VISA_CONFIG)
        tags = scraper._roles_to_tags(["Frontend Developer"])
        assert "machine-learning" in tags

    @respx.mock
    def test_missing_url_skipped(self):
        from nj.scrapers.arbeitnow import ArbeitnowScraper

        item = self._make_item(url="")
        payload = {"data": [item], "links": {}}
        respx.get("https://www.arbeitnow.com/api/job-board-api").mock(
            return_value=Response(200, json=payload)
        )
        scraper = ArbeitnowScraper(visa_config=VISA_CONFIG)
        with patch("time.sleep"):
            jobs = scraper.scrape(["ML Engineer"])
        assert jobs == []


# ── WeWorkRemotely ────────────────────────────────────────────────────────────


def _make_rss(items: list[dict]) -> str:
    root = ET.Element("rss")
    channel = ET.SubElement(root, "channel")
    for item_data in items:
        item = ET.SubElement(channel, "item")
        for tag, text in item_data.items():
            el = ET.SubElement(item, tag)
            el.text = text
    return ET.tostring(root, encoding="unicode")


class TestWeWorkRemotelyScraper:
    @respx.mock
    def test_scrape_returns_relevant_jobs(self):
        from nj.scrapers.weworkremotely import WeWorkRemotelyScraper

        rss = _make_rss(
            [
                {
                    "title": "Acme: ML Engineer",
                    "link": "https://weworkremotely.com/jobs/1",
                    "description": "PyTorch and deep learning experience required.",
                }
            ]
        )
        respx.get("https://weworkremotely.com/categories/remote-programming-jobs.rss").mock(
            return_value=Response(200, text=rss)
        )
        respx.get("https://weworkremotely.com/categories/remote-data-science-jobs.rss").mock(
            return_value=Response(200, text=_make_rss([]))
        )
        scraper = WeWorkRemotelyScraper(visa_config=VISA_CONFIG)
        with patch("time.sleep"):
            jobs = scraper.scrape(["ML Engineer"])
        assert len(jobs) >= 1
        assert jobs[0].company == "Acme"
        assert jobs[0].title == "ML Engineer"
        assert jobs[0].location == "Remote"
        assert jobs[0].source == "weworkremotely"

    @respx.mock
    def test_irrelevant_jobs_filtered_out(self):
        from nj.scrapers.weworkremotely import WeWorkRemotelyScraper

        rss = _make_rss(
            [
                {
                    "title": "Acme: Ruby on Rails Developer",
                    "link": "https://weworkremotely.com/jobs/2",
                    "description": "Build web apps with Rails.",
                }
            ]
        )
        respx.get("https://weworkremotely.com/categories/remote-programming-jobs.rss").mock(
            return_value=Response(200, text=rss)
        )
        respx.get("https://weworkremotely.com/categories/remote-data-science-jobs.rss").mock(
            return_value=Response(200, text=_make_rss([]))
        )
        scraper = WeWorkRemotelyScraper(visa_config=VISA_CONFIG)
        with patch("time.sleep"):
            jobs = scraper.scrape(["ML Engineer"])
        assert jobs == []

    @respx.mock
    def test_title_without_colon_parsed(self):
        from nj.scrapers.weworkremotely import WeWorkRemotelyScraper

        rss = _make_rss(
            [
                {
                    "title": "Machine Learning Engineer",
                    "link": "https://weworkremotely.com/jobs/3",
                    "description": "pytorch nlp llm work",
                }
            ]
        )
        respx.get("https://weworkremotely.com/categories/remote-programming-jobs.rss").mock(
            return_value=Response(200, text=rss)
        )
        respx.get("https://weworkremotely.com/categories/remote-data-science-jobs.rss").mock(
            return_value=Response(200, text=_make_rss([]))
        )
        scraper = WeWorkRemotelyScraper(visa_config=VISA_CONFIG)
        with patch("time.sleep"):
            jobs = scraper.scrape(["Machine Learning"])
        assert len(jobs) >= 1
        assert jobs[0].company == "Unknown"


# ── USAJobs ───────────────────────────────────────────────────────────────────


def _make_usajobs_response(items: list[dict]) -> dict:
    return {
        "SearchResult": {
            "SearchResultCountAll": len(items),
            "SearchResultItems": items,
        }
    }


def _make_usajobs_item(**kwargs) -> dict:
    base = {
        "MatchedObjectDescriptor": {
            "PositionTitle": "Data Scientist",
            "OrganizationName": "Department of Defense",
            "PositionURI": "https://www.usajobs.gov/job/1",
            "QualificationSummary": "Experience with machine learning required.",
            "PositionLocation": [{"CityName": "Washington", "CountrySubDivisionCode": "DC"}],
            "PositionRemuneration": [{"MinimumRange": "90000", "MaximumRange": "140000"}],
        }
    }
    if kwargs:
        base["MatchedObjectDescriptor"].update(kwargs)
    return base


class TestUSAJobsScraper:
    def test_missing_credentials_returns_empty(self):
        from nj.scrapers.usajobs import USAJobsScraper

        scraper = USAJobsScraper(api_key="", user_agent="", visa_config=VISA_CONFIG)
        jobs = scraper.scrape(["ML Engineer"])
        assert jobs == []

    def test_missing_key_only_returns_empty(self):
        from nj.scrapers.usajobs import USAJobsScraper

        scraper = USAJobsScraper(api_key="", user_agent="test@example.com", visa_config=VISA_CONFIG)
        jobs = scraper.scrape(["ML Engineer"])
        assert jobs == []

    @respx.mock
    def test_scrape_returns_jobs(self):
        from nj.scrapers.usajobs import USAJobsScraper

        payload = _make_usajobs_response([_make_usajobs_item()])
        respx.get("https://data.usajobs.gov/api/search").mock(
            return_value=Response(200, json=payload)
        )
        scraper = USAJobsScraper(
            api_key="test-key", user_agent="test@example.com", visa_config=VISA_CONFIG
        )
        with patch("time.sleep"):
            jobs = scraper.scrape(["Data Scientist"])
        assert len(jobs) >= 1
        assert jobs[0].source == "usajobs"
        assert jobs[0].company == "Department of Defense"
        assert "$90,000" in (jobs[0].salary_raw or "")
