"""Deduplication has to catch the same posting reached by two URLs.

`Job.id` hashes company+title+url, so a role syndicated to two boards is two
ids and survives as two rows — two scoring calls, and two chances to tailor the
same application twice. `description_hash` was computed by every scraper,
stored on every row, and read by nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nj.models.job import Job
from nj.utils.dedup import JobDeduplicator, content_key


class FakeRepo:
    def __init__(self, stored: set[str] | None = None) -> None:
        self.stored = stored or set()
        self.calls = 0

    def existing_ids(self, job_ids: list[str]) -> set[str]:
        self.calls += 1
        return {j for j in job_ids if j in self.stored}


def make_job(company="Acme", title="ML Engineer", url="https://a.example/1", desc="Build models."):
    return Job(
        id=Job.generate_id(company, title, url),
        title=title,
        company=company,
        url=url,
        description=desc,
        location="Remote",
        source="test",
        scraped_at=datetime.now(UTC),
        description_hash=Job.generate_hash(desc),
    )


def test_known_jobs_are_dropped() -> None:
    job = make_job()
    repo = FakeRepo({job.id})
    assert JobDeduplicator(repo).filter_new([job]) == []


def test_unknown_jobs_survive() -> None:
    job = make_job()
    assert JobDeduplicator(FakeRepo()).filter_new([job]) == [job]


def test_the_database_is_asked_once_for_the_whole_batch() -> None:
    """470 jobs used to mean 470 sessions to answer one question."""
    repo = FakeRepo()
    jobs = [make_job(url=f"https://a.example/{i}") for i in range(50)]
    JobDeduplicator(repo).filter_new(jobs)
    assert repo.calls == 1


def test_the_same_posting_on_two_boards_is_one_job() -> None:
    body = "Train and deploy computer vision models."
    a = make_job(url="https://remoteok.example/1", desc=body)
    b = make_job(url="https://weworkremotely.example/9", desc=body)
    assert a.id != b.id

    kept = JobDeduplicator(FakeRepo()).filter_new([a, b])
    assert kept == [a]


def test_a_reformatted_repost_still_collapses_on_company_and_title() -> None:
    """Falls back to normalised company+title when the body was rewritten."""
    a = make_job(company="Acme Corp.", title="ML Engineer", desc="")
    b = make_job(company="acme corp", title="ml  engineer", url="https://b.example/2", desc="")
    assert content_key(a) == content_key(b)
    assert JobDeduplicator(FakeRepo()).filter_new([a, b]) == [a]


def test_genuinely_different_roles_both_survive() -> None:
    a = make_job(title="ML Engineer", desc="Vision work.")
    b = make_job(title="Data Engineer", url="https://a.example/2", desc="Pipelines.")
    assert len(JobDeduplicator(FakeRepo()).filter_new([a, b])) == 2


def test_empty_batch_is_not_a_query() -> None:
    repo = FakeRepo()
    assert JobDeduplicator(repo).filter_new([]) == []
    assert repo.calls == 0
