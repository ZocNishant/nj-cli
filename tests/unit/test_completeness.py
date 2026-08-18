"""The guard against a tailored CV that lost content.

`anti_hallucination` deliberately allows dropping, so until this existed the
pipeline could not tell a tailoring choice from data loss. A prompt bug showed
the drafter 28% of the base CV; it returned six of thirteen sections and every
gate passed. These tests pin the direction that failure came from.
"""

from __future__ import annotations

from nj.tailoring.completeness import validate_completeness


def make_cv() -> dict:
    return {
        "personal": {"name": "Nishant Joshi"},
        "summary": "ML engineer.",
        "education": [
            {"institution": "University of South Dakota", "degree": "MSCS"},
            {"institution": "Pokhara University", "degree": "BE"},
        ],
        "skills": {"programming_languages": ["Python"]},
        "experience": [
            {"title": "ML Intern", "company": "Moffitt Cancer Center", "bullets": ["a", "b", "c"]},
            {"title": "Grad Assistant", "company": "USD", "bullets": ["d", "e"]},
        ],
        "projects": [
            {"name": "GastroVision", "anchor": True},
            {"name": "ML Inference Service"},
        ],
        "certifications": [{"name": "AWS Cloud Practitioner"}],
        "soft_skills": ["Communication"],
    }


def test_an_unchanged_cv_is_complete() -> None:
    ok, violations = validate_completeness(make_cv(), make_cv())
    assert ok is True
    assert violations == []


def test_a_dropped_section_blocks() -> None:
    """The exact shape of the shipped bug: projects present, then gone."""
    tailored = make_cv()
    del tailored["projects"]

    ok, violations = validate_completeness(make_cv(), tailored)

    assert ok is False
    assert any("projects" in v for v in violations)


def test_an_emptied_section_blocks_like_a_missing_one() -> None:
    """`projects: []` renders an empty heading — identical damage, so identical verdict."""
    tailored = make_cv()
    tailored["projects"] = []

    ok, violations = validate_completeness(make_cv(), tailored)

    assert ok is False
    assert any("projects" in v for v in violations)


def test_a_dropped_experience_entry_blocks() -> None:
    tailored = make_cv()
    tailored["experience"] = [tailored["experience"][0]]

    ok, violations = validate_completeness(make_cv(), tailored)

    assert ok is False
    assert any("USD" in v for v in violations)


def test_a_dropped_project_blocks() -> None:
    tailored = make_cv()
    tailored["projects"] = [tailored["projects"][0]]

    ok, violations = validate_completeness(make_cv(), tailored)

    assert ok is False
    assert any("ML Inference Service" in v for v in violations)


def test_trimming_bullets_is_allowed() -> None:
    """The tailoring the prompt actually asks for must not be rejected.

    "Suppress or compress less-relevant experience bullets (keep max 2)" is an
    instruction in the system prompt. If this test fails, every draft is
    rejected and the pipeline always falls back to the untailored CV.
    """
    tailored = make_cv()
    tailored["experience"][0]["bullets"] = ["a"]

    ok, violations = validate_completeness(make_cv(), tailored)

    assert ok is True
    assert violations == []


def test_reordering_is_allowed() -> None:
    tailored = make_cv()
    tailored["projects"] = list(reversed(tailored["projects"]))
    tailored["experience"] = list(reversed(tailored["experience"]))

    ok, _ = validate_completeness(make_cv(), tailored)

    assert ok is True


def test_rewording_an_entry_is_allowed() -> None:
    """Only the identifying field is compared, so prose may change freely."""
    tailored = make_cv()
    tailored["experience"][0]["title"] = "Machine Learning Intern"
    tailored["summary"] = "Completely rewritten summary targeting the role."

    ok, _ = validate_completeness(make_cv(), tailored)

    assert ok is True


def test_absent_sections_are_never_demanded() -> None:
    """A candidate with no certifications is not asked to keep certifications."""
    base = make_cv()
    del base["certifications"]
    tailored = make_cv()
    del tailored["certifications"]

    ok, violations = validate_completeness(base, tailored)

    assert ok is True
    assert violations == []


def test_an_empty_base_section_is_not_demanded() -> None:
    base = make_cv()
    base["certifications"] = []
    tailored = make_cv()
    del tailored["certifications"]

    ok, violations = validate_completeness(base, tailored)

    assert ok is True
    assert violations == []


def test_adding_content_is_not_this_validator_s_job() -> None:
    """Invention is `anti_hallucination`'s finding; overlapping would double-report."""
    tailored = make_cv()
    tailored["projects"].append({"name": "Invented Project"})

    ok, _ = validate_completeness(make_cv(), tailored)

    assert ok is True
