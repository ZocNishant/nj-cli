"""Unit tests for the job enrichment pipeline."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nj.intel.enrichment import JobEnrichment
from nj.models.job import Job, JobStatus, VisaLabel


def make_job(
    company: str = "Google",
    title: str = "ML Engineer",
    location: str = "Mountain View, CA",
) -> Job:
    return Job(
        id="test-id",
        title=title,
        company=company,
        url="https://example.com",
        description="PyTorch ML role. H1B sponsorship.",
        location=location,
        source="remoteok",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash="abc",
    )


# ---------------------------------------------------------------------------
# JobEnrichment core
# ---------------------------------------------------------------------------


def test_enrichment_returns_dict():
    enricher = JobEnrichment()
    job = make_job()
    result = enricher.enrich(job)
    assert isinstance(result, dict)
    assert "job_id" in result
    assert result["job_id"] == "test-id"


def test_enrichment_has_all_keys():
    enricher = JobEnrichment()
    job = make_job()
    result = enricher.enrich(job)
    assert "sponsorship" in result
    assert "salary" in result
    assert "semantic" in result
    assert "uscis_profile" in result
    assert "graph_context" in result


def test_enrichment_never_raises():
    enricher = JobEnrichment()
    job = make_job()
    try:
        result = enricher.enrich(job)
        assert result is not None
    except Exception as e:
        pytest.fail(f"enrich() raised an exception: {e}")


def test_enrichment_with_cv_base_never_raises():
    enricher = JobEnrichment()
    job = make_job()
    cv = {
        "skills": {"ml_frameworks": ["PyTorch"]},
        "projects": [],
        "experience": [],
        "education": [],
    }
    try:
        result = enricher.enrich(job, cv_base=cv)
        assert result is not None
    except Exception as e:
        pytest.fail(f"enrich() with cv_base raised: {e}")


# ---------------------------------------------------------------------------
# _extract_state
# ---------------------------------------------------------------------------


def test_extract_state_from_city_state():
    enricher = JobEnrichment()
    assert enricher._extract_state("San Francisco, CA") == "CA"
    assert enricher._extract_state("New York, NY") == "NY"
    assert enricher._extract_state("Austin, TX") == "TX"


def test_extract_state_remote():
    enricher = JobEnrichment()
    result = enricher._extract_state("Remote")
    assert result == "CA"


def test_extract_state_empty():
    enricher = JobEnrichment()
    result = enricher._extract_state("")
    assert result == "CA"


def test_extract_state_full_name():
    enricher = JobEnrichment()
    result = enricher._extract_state("California, United States")
    assert result == "CA"


def test_extract_state_washington():
    enricher = JobEnrichment()
    result = enricher._extract_state("Seattle, WA")
    assert result == "WA"


# ---------------------------------------------------------------------------
# enrich_batch
# ---------------------------------------------------------------------------


def test_enrich_batch_returns_dict():
    enricher = JobEnrichment()
    job1 = make_job("Google")
    job2 = make_job("Meta")
    job2.id = "test-id-2"
    result = enricher.enrich_batch([job1, job2])
    assert isinstance(result, dict)
    assert len(result) == 2
    assert "test-id" in result
    assert "test-id-2" in result


# ---------------------------------------------------------------------------
# EnrichmentRepo
# ---------------------------------------------------------------------------


def _fresh_db(tmp_path):
    import nj.db.engine as eng

    eng._engine = None
    db_path = str(tmp_path / "test.db")
    from nj.db.engine import init_db

    init_db(db_path)
    return db_path


def test_enrichment_repo_save_and_get(tmp_path):
    db_path = _fresh_db(tmp_path)
    from nj.db.repos.enrichment_repo import EnrichmentRepo

    repo = EnrichmentRepo(db_path)
    enrichment = {
        "sponsorship": {
            "probability": 0.82,
            "tier": "LIKELY_SPONSOR",
        },
        "salary": {
            "predicted_salary": 160000,
            "range": {"low": 136000, "high": 184000},
        },
        "semantic": {"score": 74.5},
        "uscis_profile": {
            "total_petitions": 250,
            "approval_rate": 92.1,
            "sponsor_tier": "STRONG",
        },
    }
    repo.save_enrichment("job-001", enrichment)
    retrieved = repo.get_enrichment("job-001")
    assert retrieved is not None
    assert retrieved["sponsorship"]["probability"] == 0.82
    assert retrieved["salary"]["predicted_salary"] == 160000
    assert retrieved["semantic"]["score"] == 74.5


def test_enrichment_repo_get_missing(tmp_path):
    db_path = _fresh_db(tmp_path)
    from nj.db.repos.enrichment_repo import EnrichmentRepo

    repo = EnrichmentRepo(db_path)
    result = repo.get_enrichment("nonexistent")
    assert result is None


def test_enrichment_repo_idempotent(tmp_path):
    db_path = _fresh_db(tmp_path)
    from nj.db.repos.enrichment_repo import EnrichmentRepo

    repo = EnrichmentRepo(db_path)
    enrichment = {
        "sponsorship": {"probability": 0.7, "tier": "LIKELY"},
        "salary": None,
        "semantic": None,
        "uscis_profile": None,
    }
    repo.save_enrichment("job-001", enrichment)
    enrichment["sponsorship"]["probability"] = 0.85
    repo.save_enrichment("job-001", enrichment)
    result = repo.get_enrichment("job-001")
    assert result["sponsorship"]["probability"] == 0.85


def test_enrichment_repo_null_fields(tmp_path):
    db_path = _fresh_db(tmp_path)
    from nj.db.repos.enrichment_repo import EnrichmentRepo

    repo = EnrichmentRepo(db_path)
    enrichment = {
        "sponsorship": None,
        "salary": None,
        "semantic": None,
        "uscis_profile": None,
    }
    repo.save_enrichment("job-002", enrichment)
    result = repo.get_enrichment("job-002")
    # Row exists but all optional fields are None
    assert result is not None
    assert result["sponsorship"] is None
    assert result["salary"] is None
