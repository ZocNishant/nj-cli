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
