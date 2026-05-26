from __future__ import annotations

from datetime import UTC, datetime

from nj.models.config import VisaConfig
from nj.models.job import Job, VisaLabel
from nj.scoring.visa_filter import VisaFilter


def make_config(**kwargs) -> VisaConfig:
    return VisaConfig(**kwargs)


def test_blocked_on_no_sponsorship():
    f = VisaFilter(make_config())
    label = f.classify("We do not offer visa sponsorship or no sponsorship available")
    assert label == VisaLabel.BLOCKED


def test_confirmed_on_h1b_keyword():
    f = VisaFilter(make_config())
    label = f.classify("We offer H1B sponsorship for qualified candidates")
    assert label == VisaLabel.CONFIRMED


def test_confirmed_on_opt_keyword():
    f = VisaFilter(make_config())
    label = f.classify("OPT candidates are welcome to apply")
    assert label == VisaLabel.CONFIRMED


def test_unknown_on_no_visa_keywords():
    f = VisaFilter(make_config())
    label = f.classify("We are looking for a senior ML engineer with 5 years experience")
    assert label == VisaLabel.UNKNOWN


def test_likely_on_international_language():
    f = VisaFilter(make_config())
    label = f.classify("We welcome international candidates from around the world")
    assert label == VisaLabel.LIKELY


def test_disabled_visa_filter_returns_unknown():
    f = VisaFilter(make_config(enabled=False))
    label = f.classify("no sponsorship available")
    assert label == VisaLabel.UNKNOWN


def test_should_skip_blocked_job():
    f = VisaFilter(make_config())
    job = Job(
        id="abc",
        title="ML Engineer",
        company="Acme",
        url="http://x.com",
        description="no sponsorship",
        location="NYC",
        source="indeed",
        visa_label=VisaLabel.BLOCKED,
        scraped_at=datetime.now(UTC),
        description_hash="xyz",
    )
    assert f.should_skip(job) is True


def test_should_not_skip_confirmed_job():
    f = VisaFilter(make_config())
    job = Job(
        id="abc",
        title="ML Engineer",
        company="Acme",
        url="http://x.com",
        description="H1B sponsorship available",
        location="NYC",
        source="indeed",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        description_hash="xyz",
    )
    assert f.should_skip(job) is False
