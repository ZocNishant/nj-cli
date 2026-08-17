"""Structural anti-hallucination checks on realistic CV shapes.

`test_tailoring.py` covers the regex layer with flat dicts. These cover the
structural pass — the one that makes the README's claim true — against the
nested shape a real `cv_base.json` has.

The invariant: tailoring may reorder, drop, or reword. It may never add a
factual claim the source CV does not contain.
"""

from __future__ import annotations

import copy

import pytest

from nj.tailoring.anti_hallucination import validate_tailored_cv

BASE_CV = {
    "personal": {"name": "Nishant Joshi"},
    "experience": [
        {
            "company": "Acme Labs",
            "title": "ML Intern",
            "bullets": ["Built a segmentation pipeline"],
        },
        {"company": "Cascade Health", "title": "Data Analyst", "bullets": []},
    ],
    "education": [
        {"institution": "University of San Diego", "degree": "MS Applied AI"},
    ],
    "projects": [
        {"name": "OncoMatch", "tech": ["PyTorch"], "bullets": ["Matched trials"]},
    ],
    "certifications": [{"name": "AWS Cloud Practitioner", "detail": "2025"}],
    "skills": {
        "ml_frameworks": ["PyTorch", "scikit-learn"],
        "programming_languages": ["Python", "C++"],
    },
}


def tailored(**overrides) -> dict:
    cv = copy.deepcopy(BASE_CV)
    cv.update(overrides)
    return cv


def assert_ok(cv: dict) -> None:
    is_valid, violations = validate_tailored_cv(BASE_CV, cv)
    assert is_valid, f"expected valid, got: {violations}"


def assert_rejected(cv: dict, expect_in_message: str) -> list[str]:
    is_valid, violations = validate_tailored_cv(BASE_CV, cv)
    assert not is_valid, "expected rejection, got a pass"
    assert any(expect_in_message.lower() in v.lower() for v in violations), violations
    return violations


# --- allowed transformations ------------------------------------------------


def test_unchanged_cv_passes():
    assert_ok(copy.deepcopy(BASE_CV))


def test_reordering_is_allowed():
    cv = tailored(
        experience=list(reversed(BASE_CV["experience"])),
        skills={
            "programming_languages": ["C++", "Python"],
            "ml_frameworks": ["scikit-learn", "PyTorch"],
        },
    )
    assert_ok(cv)


def test_dropping_entries_is_allowed():
    """Suppressing irrelevant content is the whole point of tailoring."""
    cv = tailored(
        experience=[BASE_CV["experience"][0]],
        skills={"ml_frameworks": ["PyTorch"]},
        certifications=[],
    )
    assert_ok(cv)


def test_rewording_a_bullet_is_allowed():
    cv = copy.deepcopy(BASE_CV)
    cv["experience"][0]["bullets"] = ["Designed and shipped a segmentation pipeline"]
    assert_ok(cv)


def test_casing_and_punctuation_variance_is_not_an_invention():
    cv = tailored(skills={"ml_frameworks": ["pytorch", "Scikit Learn"]})
    assert_ok(cv)


# --- rejected inventions ----------------------------------------------------


def test_invented_skill_is_rejected():
    cv = tailored(skills={"ml_frameworks": ["PyTorch", "Kubernetes"]})
    violations = assert_rejected(cv, "kubernetes")
    assert any("skill" in v.lower() for v in violations)


def test_invented_employer_is_rejected():
    cv = copy.deepcopy(BASE_CV)
    cv["experience"][0]["company"] = "Stripe"
    assert_rejected(cv, "stripe")


def test_invented_job_title_is_rejected():
    cv = copy.deepcopy(BASE_CV)
    cv["experience"][0]["title"] = "Senior Staff Engineer"
    assert_rejected(cv, "senior staff engineer")


def test_invented_institution_is_rejected():
    cv = copy.deepcopy(BASE_CV)
    cv["education"][0]["institution"] = "Stanford University"
    assert_rejected(cv, "stanford")


def test_invented_degree_is_rejected():
    cv = copy.deepcopy(BASE_CV)
    cv["education"][0]["degree"] = "PhD Computer Science"
    assert_rejected(cv, "phd")


def test_invented_project_is_rejected():
    cv = copy.deepcopy(BASE_CV)
    cv["projects"].append({"name": "Autonomous Drone Fleet", "tech": [], "bullets": []})
    assert_rejected(cv, "drone")


def test_invented_certification_is_rejected():
    cv = copy.deepcopy(BASE_CV)
    cv["certifications"].append({"name": "AWS Solutions Architect", "detail": ""})
    assert_rejected(cv, "solutions architect")


@pytest.mark.parametrize(
    "bullet, needle",
    [
        ("Worked alongside Google on this", "google"),
        ("Improved throughput by 47%", "47"),
        ("Published at NeurIPS 2024", "2024"),
        ("Holds a patent in imaging", "patent"),
    ],
)
def test_invented_free_text_claims_are_rejected(bullet: str, needle: str):
    """The regex layer catches claims that live in prose, not structured fields."""
    cv = copy.deepcopy(BASE_CV)
    cv["experience"][0]["bullets"].append(bullet)
    assert_rejected(cv, needle)


def test_violation_message_shows_original_spelling():
    """Messages must be readable — not the normalized comparison key."""
    cv = copy.deepcopy(BASE_CV)
    cv["projects"].append({"name": "Self-Driving Car", "tech": [], "bullets": []})
    _, violations = validate_tailored_cv(BASE_CV, cv)
    assert any("Self-Driving Car" in v for v in violations)


def test_multiple_inventions_are_all_reported():
    cv = copy.deepcopy(BASE_CV)
    cv["experience"][0]["company"] = "Stripe"
    cv["skills"]["ml_frameworks"].append("Kubernetes")
    is_valid, violations = validate_tailored_cv(BASE_CV, cv)
    assert not is_valid
    assert len(violations) >= 2


def test_empty_tailored_cv_is_not_an_invention():
    """Dropping everything is safe; only additions are violations."""
    is_valid, _ = validate_tailored_cv(BASE_CV, {})
    assert is_valid
