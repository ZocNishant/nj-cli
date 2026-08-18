from __future__ import annotations

from datetime import UTC, datetime

from nj.models.job import Job, JobStatus, VisaLabel
from nj.models.score import ScoreResult
from nj.tailoring.anti_hallucination import extract_entities, validate_tailored_cv
from nj.tailoring.keyword_align import extract_keywords, flatten_skills
from nj.tailoring.section_ranker import rank_projects
from nj.tailoring.suppressor import suppress_for_role


def make_job(title: str = "ML Engineer") -> Job:
    return Job(
        id="test-id",
        title=title,
        company="Acme",
        url="https://example.com",
        description="PyTorch deep learning OpenCV",
        location="USA",
        source="indeed",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash="abc",
    )


def make_score() -> ScoreResult:
    return ScoreResult(
        job_id="test-id",
        total_score=75,
        confidence=0.8,
        sub_scores=[],
        matched_skills=["PyTorch", "OpenCV"],
        missing_skills=["Kubernetes"],
        recommended_emphasis=["GastroVision", "medical imaging"],
        visa_compatible=True,
        visa_notes="OPT compatible",
        overall_rationale="Good fit.",
        scored_at=datetime.now(UTC),
        provider="claude",
        prompt_version="scoring_v1",
    )


def make_cv_base() -> dict:
    return {
        "skills": {
            "ml_frameworks": ["PyTorch", "TensorFlow"],
            "security_tools": ["Wireshark", "Metasploit"],
        },
        "projects": [
            {
                "id": "gastrovision",
                "name": "GastroVision",
                "tech": ["PyTorch"],
                "priority": 1,
                "tags": ["ml"],
                "bullets": ["Achieved 96.11% accuracy."],
            },
            {
                "id": "covid",
                "name": "COVID Tracker",
                "tech": ["React"],
                "priority": 3,
                "tags": ["web"],
                "bullets": ["Built web app."],
            },
            {
                "id": "portfolio",
                "name": "Portfolio",
                "tech": ["HTML"],
                "priority": 4,
                "tags": ["web"],
                "bullets": ["Deployed site."],
            },
        ],
        "experience": [
            {
                "id": "usd",
                "title": "Grad Assistant",
                "company": "USD",
                "location": "SD",
                "start": "Feb 2026",
                "end": "Present",
                "status": "active",
                "tags": ["it", "infrastructure"],
                "bullets": [
                    "Managed network.",
                    "Resolved alerts.",
                    "Configured Cisco.",
                    "Used SolarWinds.",
                ],
            },
        ],
    }


# --- section_ranker ---


def test_gastrovision_always_first_after_rank() -> None:
    projects = make_cv_base()["projects"]
    score = make_score()
    ranked = rank_projects(projects, score)
    assert ranked[0]["id"] == "gastrovision"


def test_rank_projects_preserves_all_projects() -> None:
    projects = make_cv_base()["projects"]
    score = make_score()
    ranked = rank_projects(projects, score)
    assert len(ranked) == len(projects)


def test_rank_projects_empty_list() -> None:
    assert rank_projects([], make_score()) == []


# --- suppressor ---


def test_security_tools_suppressed_for_ml_role() -> None:
    cv = make_cv_base()
    result = suppress_for_role(cv, make_job("ML Engineer"), make_score())
    assert "security_tools" not in result["skills"]


def test_security_tools_kept_for_non_ml_role() -> None:
    cv = make_cv_base()
    result = suppress_for_role(cv, make_job("DevOps Engineer"), make_score())
    assert "security_tools" in result["skills"]


def test_it_bullets_compressed_for_ml_role() -> None:
    cv = make_cv_base()
    result = suppress_for_role(cv, make_job("ML Engineer"), make_score())
    usd = next(e for e in result["experience"] if e["id"] == "usd")
    assert len(usd["bullets"]) <= 2


def test_suppress_does_not_mutate_original() -> None:
    cv = make_cv_base()
    original_bullets = len(cv["experience"][0]["bullets"])
    suppress_for_role(cv, make_job("ML Engineer"), make_score())
    assert len(cv["experience"][0]["bullets"]) == original_bullets


# --- keyword_align ---


def test_extract_keywords_returns_list() -> None:
    jd = "We need PyTorch expertise and TensorFlow skills for deep learning"
    keywords = extract_keywords(jd, ["Python"])
    assert isinstance(keywords, list)
    assert len(keywords) > 0


def test_extract_keywords_excludes_existing_skills() -> None:
    jd = "PyTorch and TensorFlow required"
    keywords = extract_keywords(jd, ["PyTorch", "TensorFlow"])
    assert "pytorch" not in [k.lower() for k in keywords]


def test_flatten_skills() -> None:
    skills = {
        "ml": ["PyTorch", "TensorFlow"],
        "web": ["React", "Node.js"],
    }
    flat = flatten_skills(skills)
    assert "PyTorch" in flat
    assert "React" in flat
    assert len(flat) == 4


# --- anti_hallucination ---


def test_anti_hallucination_passes_on_same_entities() -> None:
    original = {"name": "Nishant", "skills": ["PyTorch", "96.11%"]}
    tailored = {"name": "Nishant", "skills": ["PyTorch", "96.11%"], "summary": "Expert in PyTorch"}
    is_valid, violations = validate_tailored_cv(original, tailored)
    assert is_valid is True
    assert violations == []


def test_anti_hallucination_fails_on_invented_company() -> None:
    original = {"company": "USD", "skills": ["PyTorch"]}
    tailored = {"company": "USD", "skills": ["PyTorch"], "extra": "Previously worked at Google"}
    is_valid, violations = validate_tailored_cv(original, tailored)
    assert is_valid is False
    assert any("Google" in v for v in violations)


def test_anti_hallucination_fails_on_invented_metric() -> None:
    original = {"bullets": ["Achieved 96.11% accuracy"]}
    tailored = {"bullets": ["Achieved 96.11% accuracy", "Improved performance by 99.5%"]}
    is_valid, violations = validate_tailored_cv(original, tailored)
    assert is_valid is False


def test_extract_entities_finds_capitalized_words() -> None:
    cv = {"name": "Nishant", "company": "Moffitt", "score": "96.11%"}
    entities = extract_entities(cv)
    assert "Nishant" in entities
    assert "Moffitt" in entities
    assert "96.11%" in entities


# --- application logging ---------------------------------------------------
#
# `nj tailor` wrote the PDF, the letter and the JSON, and wrote nothing to the
# applications table. The promotion path is
# `nj status --update-id <id> --update-status submitted`, and that id was only
# ever created by `cmd_run` — so the moment a human sent a tailored CV, the
# system had no memory of it. No applied_at, so the daily cap counted zero; no
# row on the dashboard; and nothing for an interview or rejection to attach to,
# which is why the outcome analytics have never had data to read.


def _repo(tmp_path):
    from nj.db.repos.application_repo import ApplicationRepo

    return ApplicationRepo(str(tmp_path / "apps.db"))


def _record(repo, job=None, score=77, pdf="output/cv.pdf", cover="output/cv_cover.txt"):
    from nj.cli.cmd_tailor import _record_application

    _record_application(
        app_repo=repo,
        job=job or make_job(),
        score=score,
        pdf_path=pdf,
        cover_path=cover,
    )


def test_a_rendered_packet_is_logged(tmp_path) -> None:
    repo = _repo(tmp_path)
    _record(repo)

    apps = repo.get_applications()
    assert len(apps) == 1
    assert apps[0].job_id == make_job().id
    assert apps[0].cv_path == "output/cv.pdf"
    assert apps[0].cover_letter_path == "output/cv_cover.txt"
    assert apps[0].score == 77


def test_the_logged_row_is_generated_never_submitted(tmp_path) -> None:
    """nj cannot send anything. Only a human promotes a row."""
    from nj.models.application import ApplicationStatus

    repo = _repo(tmp_path)
    _record(repo)
    assert repo.get_applications()[0].status is ApplicationStatus.GENERATED


def test_applied_at_is_stamped_so_the_daily_cap_can_count_it(tmp_path) -> None:
    """count_today() filters on applied_at; unset, max_per_day never fires."""
    repo = _repo(tmp_path)
    _record(repo)

    assert repo.get_applications()[0].applied_at is not None
    assert repo.count_today() == 1


def test_the_row_carries_an_id_status_can_promote(tmp_path) -> None:
    """The whole point: an id for --update-id to target."""
    from nj.models.application import ApplicationStatus

    repo = _repo(tmp_path)
    _record(repo)

    app_id = repo.get_applications()[0].id
    repo.update_status(app_id, ApplicationStatus.SUBMITTED)
    assert repo.get_applications()[0].status is ApplicationStatus.SUBMITTED


def test_a_failed_render_is_not_logged_as_an_application(tmp_path) -> None:
    """GENERATED asserts a CV is on disk. Without a PDF there is nothing to send."""
    repo = _repo(tmp_path)
    _record(repo, pdf=None)
    assert repo.get_applications() == []


def test_an_over_budget_render_is_not_logged(tmp_path) -> None:
    """PageBudgetError leaves pdf_path unset — the file exists but is not sendable."""
    repo = _repo(tmp_path)
    _record(repo, pdf=None, cover="output/cv_cover.txt")
    assert repo.count_today() == 0


def test_a_missing_cover_letter_still_logs_the_cv(tmp_path) -> None:
    """A letter can fail while the CV is perfectly sendable."""
    repo = _repo(tmp_path)
    _record(repo, cover=None)

    apps = repo.get_applications()
    assert len(apps) == 1
    assert apps[0].cover_letter_path is None


def test_retailoring_the_same_job_does_not_duplicate_the_row(tmp_path) -> None:
    """Two rows would double-count against max_per_day and show twice on the
    dashboard."""
    repo = _repo(tmp_path)
    _record(repo, pdf="output/v1.pdf", score=70)
    _record(repo, pdf="output/v2.pdf", score=85)

    apps = repo.get_applications()
    assert len(apps) == 1
    assert apps[0].cv_path == "output/v2.pdf"
    assert apps[0].score == 85
    assert repo.count_today() == 1


def test_retailoring_never_retracts_a_submitted_application(tmp_path) -> None:
    """A human asserted they sent this. Regenerating the packet must not
    silently un-assert it."""
    from nj.models.application import ApplicationStatus

    repo = _repo(tmp_path)
    _record(repo, pdf="output/v1.pdf")
    app_id = repo.get_applications()[0].id
    repo.update_status(app_id, ApplicationStatus.SUBMITTED)

    _record(repo, pdf="output/v2.pdf")

    apps = repo.get_applications()
    assert len(apps) == 1
    assert apps[0].status is ApplicationStatus.SUBMITTED
    assert apps[0].cv_path == "output/v2.pdf"


def test_two_different_jobs_get_two_rows(tmp_path) -> None:
    """Deduplication is per job id, not global — make_job() pins one id, so
    these have to be built separately."""
    repo = _repo(tmp_path)

    first = make_job(title="ML Engineer")
    second = make_job(title="Research Engineer")
    second.id = "test-id-2"

    _record(repo, job=first)
    _record(repo, job=second)

    apps = repo.get_applications()
    assert len(apps) == 2
    assert {a.job_id for a in apps} == {"test-id", "test-id-2"}


def test_get_by_job_id_returns_none_for_an_unknown_job(tmp_path) -> None:
    assert _repo(tmp_path).get_by_job_id("no-such-job") is None


def test_run_tailor_end_to_end_logs_the_application(tmp_path, monkeypatch) -> None:
    """Drives run_tailor itself, not the helper.

    The tests above call `_record_application` directly, so deleting the call
    site from `run_tailor` — which *is* the original bug — leaves every one of
    them green. This is the one that fails if the wiring goes away.
    """
    import json as _json

    from nj.db.repos.application_repo import ApplicationRepo
    from nj.db.repos.job_repo import JobRepo
    from nj.models.application import ApplicationStatus

    monkeypatch.chdir(tmp_path)
    (tmp_path / "cv").mkdir()
    (tmp_path / "cv" / "cv_base.json").write_text(_json.dumps(make_cv_base()))
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "cv_template.tex").write_text("stub")

    db_path = str(tmp_path / "nj.db")
    job = make_job()
    JobRepo(db_path).save_job(job)

    async def fake_score_job(*a, **k):
        return make_score()

    async def fake_tailor_cv(*a, **k):
        return make_cv_base(), "Dear Hiring Manager, ..."

    async def fake_cover(*a, **k):
        return "output/letter.txt"

    monkeypatch.setattr("nj.scoring.scorer.score_job", fake_score_job)
    monkeypatch.setattr("nj.tailoring.tailor.tailor_cv", fake_tailor_cv)
    monkeypatch.setattr("nj.tailoring.cover_letter.generate_and_save_cover_letter", fake_cover)
    monkeypatch.setattr("nj.tailoring.renderer.render_cv", lambda **k: "output/cv.pdf")
    monkeypatch.setattr("nj.providers.registry.get_provider", lambda *a, **k: object())

    from nj.cli.cmd_tailor import run_tailor
    from nj.models.config import Config

    run_tailor(url=None, config=Config(), db_path=db_path, job_id=job.id)

    apps = ApplicationRepo(db_path).get_applications()
    assert len(apps) == 1, "run_tailor produced a packet but logged no application"
    assert apps[0].status is ApplicationStatus.GENERATED
    assert apps[0].cv_path == "output/cv.pdf"
    assert apps[0].applied_at is not None
