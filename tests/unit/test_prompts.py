from __future__ import annotations

from nj.prompts import cover_letter_v1, intern_update_v1, scoring_v1, tailoring_v1

_SAMPLE_CV = {
    "personal": {
        "name": "Alex Smith",
        "visa_status": "opt",
        "work_authorization": "F-1 OPT eligible June 2026",
        "graduation_date": "June 2026",
    },
    "education": [{"degree": "MSCS", "institution": "State University"}],
    "skills": {"ml": ["PyTorch", "TensorFlow"], "tools": ["Docker", "FastAPI"]},
    "projects": [
        {
            "name": "MedVision",
            "anchor": True,
            "tags": ["ml", "cv"],
            "tech": ["PyTorch"],
            "bullets": ["Achieved 95% accuracy on medical image dataset"],
        }
    ],
    "experience": [
        {
            "title": "ML Intern",
            "company": "Research Institute",
            "status": "incoming",
            "start": "June 2026",
        }
    ],
}


def test_scoring_system_prompt_contains_key_rules() -> None:
    p = scoring_v1.SYSTEM_PROMPT
    assert "skills_match" in p
    assert "sponsorship_compatibility" in p
    assert "JSON" in p


def test_scoring_build_user_prompt_includes_job_title() -> None:
    prompt = scoring_v1.build_user_prompt(
        job_title="ML Engineer",
        job_description="We need PyTorch expertise and computer vision skills.",
        skills={"ml_frameworks": ["PyTorch", "TensorFlow"]},
        top_projects=[
            {
                "name": "MedVision",
                "tech": ["PyTorch"],
                "bullets": ["Achieved 95% accuracy"],
            }
        ],
        cv_base=_SAMPLE_CV,
    )
    assert "ML Engineer" in prompt
    assert "PyTorch" in prompt
    assert "MedVision" in prompt
    assert "Alex Smith" in prompt


def test_scoring_build_user_prompt_injects_candidate_context() -> None:
    prompt = scoring_v1.build_user_prompt(
        job_title="AI Engineer",
        job_description="Deep learning role.",
        skills={},
        top_projects=[],
        cv_base=_SAMPLE_CV,
    )
    assert "Alex Smith" in prompt
    assert "F-1 OPT" in prompt
    assert "MedVision" in prompt


def test_scoring_truncates_long_description() -> None:
    long_desc = "x" * 5000
    prompt = scoring_v1.build_user_prompt(
        job_title="Test",
        job_description=long_desc,
        skills={},
        top_projects=[],
    )
    assert len(prompt) < 6000


def test_tailoring_system_prompt_contains_anti_hallucination() -> None:
    p = tailoring_v1.SYSTEM_PROMPT
    assert "NEVER" in p
    assert "anchor" in p.lower()
    assert "incoming" in p


def test_tailoring_build_user_prompt_includes_company() -> None:
    prompt = tailoring_v1.build_user_prompt(
        job_title="CV Engineer",
        job_company="Acme Corp",
        job_description="We need OpenCV and PyTorch skills.",
        score_result={
            "matched_skills": ["PyTorch"],
            "missing_skills": [],
            "recommended_emphasis": ["MedVision"],
        },
        cv_base=_SAMPLE_CV,
        keywords=["OpenCV", "PyTorch", "deep learning"],
    )
    assert "Acme Corp" in prompt
    assert "OpenCV" in prompt
    assert "MedVision" in prompt


def test_cover_letter_system_prompt_bans_passion() -> None:
    p = cover_letter_v1.SYSTEM_PROMPT
    assert "passionate" in p.lower()
    assert "3 paragraphs" in p or "3-paragraph" in p or "3 paragraph" in p


def test_cover_letter_system_prompt_carries_the_candidate_facts() -> None:
    """The candidate's facts belong in the operator-authored turn."""
    system = cover_letter_v1.build_system_prompt(_SAMPLE_CV)
    assert "MedVision" in system
    assert "F-1 OPT" in system
    assert "Research Institute" in system


def test_cover_letter_system_prompt_without_cv_is_the_bare_instructions() -> None:
    assert cover_letter_v1.build_system_prompt(None) == cover_letter_v1.SYSTEM_PROMPT
    assert cover_letter_v1.build_system_prompt({}) == cover_letter_v1.SYSTEM_PROMPT


def test_cover_letter_user_prompt_keeps_cv_out_of_the_untrusted_turn() -> None:
    """A posting must never share a turn with the facts it might try to amend."""
    prompt = cover_letter_v1.build_user_prompt(
        job_title="ML Engineer",
        job_company="DeepMind",
        job_description="Reinforcement learning and computer vision.",
        matched_skills=["PyTorch", "OpenCV"],
        overall_rationale="Strong CV match on computer vision.",
        cv_base=_SAMPLE_CV,
    )
    assert "DeepMind" in prompt
    assert "MedVision" not in prompt
    assert "F-1 OPT" not in prompt
    assert "Research Institute" not in prompt


def test_tailoring_system_prompt_carries_the_cv() -> None:
    system = tailoring_v1.build_system_prompt(_SAMPLE_CV)
    assert "MedVision" in system
    assert "Research Institute" in system
    assert "anchor project" in system


def test_tailoring_system_prompt_without_cv_is_the_bare_instructions() -> None:
    assert tailoring_v1.build_system_prompt(None) == tailoring_v1.SYSTEM_PROMPT
    assert tailoring_v1.build_system_prompt({}) == tailoring_v1.SYSTEM_PROMPT


def test_tailoring_user_prompt_keeps_cv_out_of_the_untrusted_turn() -> None:
    prompt = tailoring_v1.build_user_prompt(
        job_title="CV Engineer",
        job_company="Acme Corp",
        job_description="We need OpenCV and PyTorch skills.",
        score_result={"matched_skills": [], "missing_skills": [], "recommended_emphasis": []},
        cv_base=_SAMPLE_CV,
        keywords=["OpenCV"],
    )
    assert "Acme Corp" in prompt
    assert "Research Institute" not in prompt
    assert "State University" not in prompt


def test_cover_letter_build_user_prompt_no_cv_base() -> None:
    prompt = cover_letter_v1.build_user_prompt(
        job_title="ML Engineer",
        job_company="DeepMind",
        job_description="Computer vision role.",
        matched_skills=["PyTorch"],
        overall_rationale="Good match.",
    )
    assert "DeepMind" in prompt


def test_intern_update_returns_json_instruction() -> None:
    prompt = intern_update_v1.build_user_prompt(
        "I worked on segmentation models for CT scans using PyTorch"
    )
    assert "JSON array" in prompt
    assert "Moffitt" in prompt
    assert "action verb" in prompt


def test_prompt_versions_are_strings() -> None:
    assert isinstance(scoring_v1.PROMPT_VERSION, str)
    assert isinstance(tailoring_v1.PROMPT_VERSION, str)
    assert isinstance(cover_letter_v1.PROMPT_VERSION, str)
    assert isinstance(intern_update_v1.PROMPT_VERSION, str)
