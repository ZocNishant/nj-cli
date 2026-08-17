from __future__ import annotations

from datetime import UTC, datetime

from nj.models.config import VisaConfig
from nj.models.job import Job, VisaLabel
from nj.scoring.visa_filter import VisaFilter


def make_config(**kwargs) -> VisaConfig:
    return VisaConfig(**kwargs)


# Regression tests for the two-way misclassification the substring matcher had.
# Both directions were expensive: the first dropped employers that would have
# sponsored, the second spent credit and applications on ones that never would.


def test_authorization_requirement_alone_is_not_a_block():
    """ "Must be authorized to work in the US" is satisfied by OPT.

    Nearly every US posting contains this sentence. Treating it as a block
    silently discarded most of the market.
    """
    f = VisaFilter(make_config())
    label, _ = f.explain("Applicants must be legally authorized to work in the United States.")
    assert label == VisaLabel.UNKNOWN


def test_sponsoring_employer_that_also_requires_authorization():
    f = VisaFilter(make_config())
    label, why = f.explain(
        "We sponsor H-1B visas. Candidates must be authorized to work in the "
        "United States at the time of hire."
    )
    assert label == VisaLabel.CONFIRMED, why


def test_authorization_without_sponsorship_is_a_block():
    f = VisaFilter(make_config())
    label, _ = f.explain(
        "Must be authorized to work in the U.S. without sponsorship now or in the future."
    )
    assert label == VisaLabel.BLOCKED


def test_negated_sponsorship_is_not_read_as_an_offer():
    """ "We do not sponsor" used to classify as CONFIRMED."""
    f = VisaFilter(make_config())
    for text in (
        "We do not sponsor employment visas.",
        "We are unable to provide visa sponsorship for this role.",
        "This role does not offer sponsorship.",
    ):
        assert f.classify(text) == VisaLabel.BLOCKED, text


def test_citizenship_and_clearance_gates_are_blocks():
    f = VisaFilter(make_config())
    for text in (
        "US citizenship is required.",
        "This position requires an active security clearance.",
        "Green card holders only.",
    ):
        assert f.classify(text) == VisaLabel.BLOCKED, text


def test_opt_acronym_does_not_match_opt_in():
    """Bare substring matching on "opt" fired on "opt-in" and "options"."""
    f = VisaFilter(make_config())
    label = f.classify("Opt-in to our talent community. Generous stock options.")
    assert label == VisaLabel.UNKNOWN


def test_explain_returns_the_deciding_evidence():
    f = VisaFilter(make_config())
    label, why = f.explain("We do not sponsor employment visas.")
    assert label == VisaLabel.BLOCKED
    assert "sponsor" in why.lower()


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
