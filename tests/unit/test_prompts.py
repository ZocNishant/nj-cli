from __future__ import annotations

from nj.prompts import cover_letter_v1, intern_update_v1, scoring_v1, tailoring_v1


def test_scoring_system_prompt_contains_key_rules() -> None:
    p = scoring_v1.SYSTEM_PROMPT
    assert "skills_match" in p
    assert "sponsorship_compatibility" in p
    assert "GastroVision" in p
    assert "JSON" in p
    assert "F-1 OPT" in p


def test_scoring_build_user_prompt_includes_job_title() -> None:
    prompt = scoring_v1.build_user_prompt(
        job_title="ML Engineer",
        job_description="We need PyTorch expertise and computer vision skills.",
        skills={"ml_frameworks": ["PyTorch", "TensorFlow"]},
        top_projects=[
            {
                "name": "GastroVision",
                "tech": ["PyTorch"],
                "bullets": ["Achieved 96% accuracy"],
            }
        ],
    )
    assert "ML Engineer" in prompt
    assert "PyTorch" in prompt
    assert "GastroVision" in prompt


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
    assert "GastroVision" in p
    assert "incoming" in p


def test_tailoring_build_user_prompt_includes_company() -> None:
    prompt = tailoring_v1.build_user_prompt(
        job_title="CV Engineer",
        job_company="Acme Corp",
        job_description="We need OpenCV and PyTorch skills.",
        score_result={
            "matched_skills": ["PyTorch"],
            "missing_skills": [],
            "recommended_emphasis": ["GastroVision"],
        },
        cv_base={"personal": {"name": "Nishant Joshi"}, "skills": {}},
        keywords=["OpenCV", "PyTorch", "deep learning"],
    )
    assert "Acme Corp" in prompt
    assert "OpenCV" in prompt


def test_cover_letter_system_prompt_bans_passion() -> None:
    p = cover_letter_v1.SYSTEM_PROMPT
    assert "passionate" in p.lower()
    assert "3 paragraphs" in p or "3-paragraph" in p or "3 paragraph" in p


def test_cover_letter_build_user_prompt_includes_gastrovision() -> None:
    prompt = cover_letter_v1.build_user_prompt(
        job_title="ML Engineer",
        job_company="DeepMind",
        job_description="Reinforcement learning and computer vision.",
        matched_skills=["PyTorch", "OpenCV"],
        overall_rationale="Strong CV match on computer vision.",
    )
    assert "GastroVision" in prompt
    assert "DeepMind" in prompt
    assert "Moffitt" in prompt


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
