from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nj.tailoring.renderer import (
    RendererError,
    _fill_template,
    _render_experience,
    _render_gap,
    _render_projects,
    _render_skills,
    _render_summary,
    _safe_filename,
    render_cv,
)
from nj.utils.text import escape_latex


def make_cv() -> dict:
    return {
        "personal": {
            "name": "Nishant Joshi",
            "location": "Vermillion, SD",
            "phone": "+1 (656) 247-8411",
            "email": "zocnishant@gmail.com",
            "linkedin": "linkedin.com/in/nishant-joshi",
            "github": "github.com/ZocNishant",
        },
        "summary": "ML engineer specializing in computer vision.",
        "education": [
            {
                "institution": "University of South Dakota",
                "location": "Vermillion, SD",
                "degree": "Master of Science in Computer Science",
                "start": "August 2024",
                "end": "December 2026 (Expected)",
                "courses": ["Machine Learning", "Computer Vision"],
            }
        ],
        "skills": {
            "ml_frameworks": ["PyTorch", "TensorFlow"],
            "programming_languages": ["Python", "C++"],
        },
        "experience": [
            {
                "id": "moffitt",
                "title": "Machine Learning Intern",
                "company": "Moffitt Cancer Center",
                "location": "Tampa, FL",
                "start": "June 2026",
                "end": "Present",
                "status": "incoming",
                "bullets": [],
                "tags": ["ml"],
            },
            {
                "id": "usd",
                "title": "Graduate Assistant",
                "company": "University of South Dakota",
                "location": "Vermillion, SD",
                "start": "February 2026",
                "end": "Present",
                "status": "active",
                "bullets": ["Managed network infrastructure."],
                "tags": ["it"],
            },
        ],
        "projects": [
            {
                "id": "gastrovision",
                "name": "GastroVision",
                "tech": ["PyTorch", "EfficientNet"],
                "date": "December 2024",
                "bullets": ["Achieved 96.11% accuracy."],
            }
        ],
        "gap_explanation": {
            "period": "March 2022 -- April 2023",
            "reason": "Dedicated time to family matters.",
        },
        "research_interests": ["Computer Vision", "Medical Imaging"],
        "memberships": [{"name": "IEEE", "detail": "Member No. 100392414"}],
        "certifications": [
            {"name": "Google Cybersecurity", "detail": "Foundations", "date": "April 2024"}
        ],
        "soft_skills": ["Communication", "Leadership"],
    }


def make_template() -> str:
    return (
        "\\begin{document}\n"
        "%%NAME%% %%EMAIL%%\n"
        "%%SUMMARY_BLOCK%%\n"
        "%%EDUCATION_BLOCK%%\n"
        "%%SKILLS_BLOCK%%\n"
        "%%EXPERIENCE_BLOCK%%\n"
        "%%GAP_BLOCK%%\n"
        "%%RESEARCH_INTERESTS%%\n"
        "%%PROJECTS_BLOCK%%\n"
        "%%MEMBERSHIPS_BLOCK%%\n"
        "%%CERTIFICATIONS_BLOCK%%\n"
        "%%SOFT_SKILLS%%\n"
        "\\end{document}"
    )


# --- _fill_template ---


def test_fill_template_replaces_name() -> None:
    result = _fill_template(make_template(), make_cv())
    assert "Nishant Joshi" in result
    assert "%%NAME%%" not in result


def test_fill_template_no_placeholders_remain() -> None:
    result = _fill_template(make_template(), make_cv())
    assert "%%" not in result


# --- _render_summary ---


def test_render_summary_empty_returns_empty() -> None:
    assert _render_summary("") == ""
    assert _render_summary("   ") == ""


def test_render_summary_wraps_in_section() -> None:
    result = _render_summary("Expert in PyTorch.")
    assert "\\section{Summary}" in result
    assert "Expert in PyTorch." in result


# --- _render_skills ---


def test_render_skills_includes_labels() -> None:
    skills = {"ml_frameworks": ["PyTorch", "TensorFlow"]}
    result = _render_skills(skills)
    assert "ML/AI Frameworks" in result
    assert "PyTorch" in result


def test_render_skills_skips_empty_categories() -> None:
    skills = {"ml_frameworks": [], "programming_languages": ["Python"]}
    result = _render_skills(skills)
    assert "ML/AI Frameworks" not in result
    assert "Python" in result


# --- _render_experience ---


def test_moffitt_incoming_renders_without_bullets() -> None:
    exp = [make_cv()["experience"][0]]
    result = _render_experience(exp)
    assert "Incoming" in result
    assert "\\resumeItem{\\textit{Incoming" in result or "incoming" in result.lower()


def test_active_experience_renders_bullets() -> None:
    exp = [make_cv()["experience"][1]]
    result = _render_experience(exp)
    assert "Managed network infrastructure" in result


# --- _render_projects ---


def test_render_projects_includes_gastrovision() -> None:
    projects = make_cv()["projects"]
    result = _render_projects(projects)
    assert "GastroVision" in result
    assert "96.11" in result


# --- _render_gap ---


def test_render_gap_returns_empty_when_none() -> None:
    assert _render_gap(None) == ""


def test_render_gap_includes_period() -> None:
    gap = {"period": "March 2022 -- April 2023", "reason": "Family matters."}
    result = _render_gap(gap)
    assert "March 2022" in result
    assert "Family matters" in result


# --- _safe_filename ---


def test_safe_filename_removes_special_chars() -> None:
    result = _safe_filename("Acme Corp & Partners!")
    assert " " not in result
    assert "&" not in result
    assert "!" not in result


def test_safe_filename_truncates_to_30() -> None:
    result = _safe_filename("a" * 50)
    assert len(result) <= 30


# --- escape_latex ---


def test_escape_latex_ampersand() -> None:
    assert "\\&" in escape_latex("R&D")


def test_escape_latex_percent() -> None:
    assert "\\%" in escape_latex("96.11% accuracy")


# --- render_cv ---


def test_render_cv_raises_on_missing_tectonic(tmp_path: Path) -> None:
    template_file = tmp_path / "template.tex"
    template_file.write_text(make_template())
    with patch("nj.tailoring.renderer.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="not found")
        with pytest.raises(RendererError):
            render_cv(
                cv_data=make_cv(),
                template_path=str(template_file),
                output_dir=str(tmp_path / "output"),
                company="Acme",
                job_title="ML Engineer",
            )


def test_render_cv_returns_pdf_path_on_success(tmp_path: Path) -> None:
    template_file = tmp_path / "template.tex"
    template_file.write_text(make_template())
    output_dir = tmp_path / "output"

    def fake_run(cmd, **kwargs):
        tex_path = next(a for a in cmd if a.endswith(".tex"))
        pdf_path = tex_path.replace(".tex", ".pdf")
        Path(pdf_path).write_text("fake pdf")
        return MagicMock(returncode=0, stderr="")

    with patch("nj.tailoring.renderer.subprocess.run", side_effect=fake_run):
        path = render_cv(
            cv_data=make_cv(),
            template_path=str(template_file),
            output_dir=str(output_dir),
            company="Acme",
            job_title="ML Engineer",
        )
        assert path.endswith(".pdf")
        assert Path(path).exists()
