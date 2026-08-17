from __future__ import annotations

import inspect
import json
import os
import re
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nj.tailoring.renderer import (
    PageBudgetError,
    RendererError,
    _fill_template,
    _render_experience,
    _render_gap,
    _render_projects,
    _render_skills,
    _render_summary,
    _safe_filename,
    _safe_url,
    page_count,
    render_cv,
    verify_page_budget,
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


# --- the shipped template ---
#
# Everything above this line uses make_template(), a synthetic template built by
# the test. That is why `templates/cv_template.tex` could sit at 0 bytes for
# months with a fully green suite: nothing asserted against the file that
# actually ships. These tests read the real file.
#
# None of them compile it — tectonic is a system binary and CI does not have
# one. Filling is where the silent failures live; a broken .tex fails loudly.

SHIPPED_TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "cv_template.tex"

PLACEHOLDER_RE = re.compile(r"%%[A-Z_]+%%")


def _renderer_placeholders() -> set[str]:
    """The tokens _fill_template will substitute, read off its own source.

    Derived rather than hardcoded so that adding a placeholder to the renderer
    without adding it to the template fails here instead of silently dropping
    that section from every CV.
    """
    return set(PLACEHOLDER_RE.findall(inspect.getsource(_fill_template)))


def test_shipped_template_is_not_empty() -> None:
    """The 0-byte regression, asserted directly.

    An empty template renders an empty document and every substitution becomes a
    no-op, which is invisible to any test that only checks for leftover tokens —
    a file with no content also has no placeholders.
    """
    assert SHIPPED_TEMPLATE.exists(), f"{SHIPPED_TEMPLATE} is missing"
    body = SHIPPED_TEMPLATE.read_text(encoding="utf-8")
    assert body.strip(), "templates/cv_template.tex is empty"
    assert "\\begin{document}" in body
    assert "\\end{document}" in body


def test_shipped_template_declares_every_placeholder_the_renderer_substitutes() -> None:
    body = SHIPPED_TEMPLATE.read_text(encoding="utf-8")
    missing = sorted(tok for tok in _renderer_placeholders() if tok not in body)
    assert not missing, (
        f"_fill_template substitutes {missing} but the template never uses them, "
        "so that content is dropped from every rendered CV"
    )


def test_shipped_template_fills_with_nothing_left_over() -> None:
    filled = _fill_template(SHIPPED_TEMPLATE.read_text(encoding="utf-8"), make_cv())
    leftover = sorted(set(PLACEHOLDER_RE.findall(filled)))
    assert not leftover, f"unsubstituted placeholders survived the fill: {leftover}"


def test_shipped_template_actually_carries_the_cv_content() -> None:
    """The assertion that makes the one above mean something.

    "No placeholders remain" is trivially true of an empty file, so on its own
    it would have passed against the 0-byte template. This pins that each block
    reached the output.
    """
    filled = _fill_template(SHIPPED_TEMPLATE.read_text(encoding="utf-8"), make_cv())
    for fragment in (
        "Nishant Joshi",  # NAME
        "zocnishant@gmail.com",  # EMAIL
        "ML engineer specializing",  # SUMMARY_BLOCK
        "University of South Dakota",  # EDUCATION_BLOCK
        "PyTorch",  # SKILLS_BLOCK
        "Machine Learning Intern",  # EXPERIENCE_BLOCK
        "GastroVision",  # PROJECTS_BLOCK
        "Dedicated time to family matters",  # GAP_BLOCK
        "Medical Imaging",  # RESEARCH_INTERESTS
        "IEEE",  # MEMBERSHIPS_BLOCK
        "Google Cybersecurity",  # CERTIFICATIONS_BLOCK
        "Communication",  # SOFT_SKILLS
    ):
        assert fragment in filled, f"{fragment!r} never reached the rendered .tex"


REAL_CV = Path(__file__).resolve().parents[2] / "cv" / "cv_base.json"


def _require_tectonic() -> None:
    """Skip locally when the LaTeX toolchain is absent; fail when CI demands it.

    tectonic is a system binary, so a clean laptop checkout does not have one
    and these tests skip rather than fail there. CI sets NJ_REQUIRE_TECTONIC=1,
    which turns the skip into a failure — a silently skipped check is how the
    0-byte template survived for months.

    Called from inside each test rather than used as a skipif condition: a
    pytest.fail in a decorator argument runs at collection time and takes the
    whole module down with it, so a missing compiler would also destroy the
    signal from every other renderer test.
    """
    if shutil.which("tectonic"):
        return
    if os.getenv("NJ_REQUIRE_TECTONIC") == "1":
        pytest.fail("NJ_REQUIRE_TECTONIC=1 but tectonic is not installed")
    pytest.skip("tectonic not installed")


@pytest.mark.skipif(not REAL_CV.exists(), reason="cv/cv_base.json is gitignored; local only")
def test_shipped_template_fills_against_the_real_cv() -> None:
    """Same contract as the fixture test, against the operator's actual CV.

    The fixture populates every block by construction. A real CV does not — the
    base CV carries summary="" — so this catches a shape the fixture cannot:
    a key the renderer expects that the real file spells differently.
    """
    cv = json.loads(REAL_CV.read_text(encoding="utf-8"))
    filled = _fill_template(SHIPPED_TEMPLATE.read_text(encoding="utf-8"), cv)
    leftover = sorted(set(PLACEHOLDER_RE.findall(filled)))
    assert not leftover, f"unsubstituted placeholders against the real CV: {leftover}"
    assert cv["personal"]["name"] in filled


def test_shipped_template_compiles(tmp_path: Path) -> None:
    """The shipped template must produce a real PDF, not just fill cleanly.

    Goes through render_cv rather than calling tectonic directly so the fill,
    the compile and verify_page_budget are all exercised on the path cmd_run
    actually takes.
    """
    _require_tectonic()
    pdf = render_cv(
        cv_data=make_cv(),
        template_path=str(SHIPPED_TEMPLATE),
        output_dir=str(tmp_path),
        company="CI",
        job_title="Template Check",
    )
    out = Path(pdf)
    assert out.exists() and out.suffix == ".pdf"
    assert out.stat().st_size > 1000, "PDF is suspiciously small — template may be near-empty"
    assert page_count(str(out)) in (1, 2)


def test_shipped_template_compiles_with_every_optional_section_empty(tmp_path: Path) -> None:
    """A CV missing every optional section must still compile.

    The list macros in the template are \\begingroup rather than itemize
    precisely because the _render_* helpers emit nothing for an empty section,
    and an empty itemize is a hard LaTeX error. Someone "tidying" those macros
    into a normal itemize would pass every fill test and break this one.
    """
    _require_tectonic()
    bare = make_cv()
    for key in ("education", "experience", "projects", "certifications", "memberships"):
        bare[key] = []
    bare["skills"] = {}
    bare["research_interests"] = []
    bare["soft_skills"] = []
    bare["summary"] = ""
    bare["gap_explanation"] = None

    pdf = render_cv(
        cv_data=bare,
        template_path=str(SHIPPED_TEMPLATE),
        output_dir=str(tmp_path),
        company="CI",
        job_title="Empty Sections",
    )
    assert Path(pdf).exists()


def test_shipped_template_has_no_placeholder_tokens_inside_comments() -> None:
    """A placeholder named in a comment expands into live LaTeX.

    _fill_template does a blind string replace over the whole file, so a token
    written inside a `%` comment is substituted too. The first line of the
    injected block stays commented out and every line after it does not — which
    is how a GAP_BLOCK mentioned in a comment once dropped
    \\resumeSubHeadingListStart above the preamble that defines it.
    """
    offenders = []
    for lineno, line in enumerate(
        SHIPPED_TEMPLATE.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not PLACEHOLDER_RE.search(line):
            continue
        # A line that is *only* a placeholder collapses to empty here. A comment
        # that happens to mention one still starts with % once they are removed.
        if PLACEHOLDER_RE.sub("", line).strip().startswith("%"):
            offenders.append(f"  line {lineno}: {line.strip()}")
    assert not offenders, "placeholder tokens named inside comments:\n" + "\n".join(offenders)


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


# --- page budget ---


def write_pdf(path: Path, pages: int) -> Path:
    """A real, minimal PDF with `pages` blank pages."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with open(path, "wb") as f:
        writer.write(f)
    return path


def test_page_count_reads_a_real_pdf(tmp_path: Path) -> None:
    assert page_count(str(write_pdf(tmp_path / "two.pdf", 2))) == 2


def test_page_count_returns_none_for_a_non_pdf(tmp_path: Path) -> None:
    """Unreadable is not zero — the caller must be able to tell them apart."""
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf")
    assert page_count(str(bad)) is None


def test_two_pages_is_within_budget(tmp_path: Path) -> None:
    assert verify_page_budget(str(write_pdf(tmp_path / "cv.pdf", 2))) == 2


def test_three_pages_raises(tmp_path: Path) -> None:
    """Orphan spillover onto a third page must not reach a recruiter."""
    pdf = write_pdf(tmp_path / "cv.pdf", 3)
    with pytest.raises(PageBudgetError) as exc:
        verify_page_budget(str(pdf))
    assert exc.value.pages == 3
    assert exc.value.max_pages == 2
    # The overflowing file stays put so the operator can see what spilled.
    assert Path(exc.value.pdf_path).exists()


def test_reference_pages_can_tighten_the_budget_but_not_loosen_it(tmp_path: Path) -> None:
    two = str(write_pdf(tmp_path / "two.pdf", 2))
    # A one-page base CV means a two-page tailored CV has grown: reject.
    with pytest.raises(PageBudgetError):
        verify_page_budget(two, reference_pages=1)
    # A four-page base CV does not license a four-page tailored CV.
    assert verify_page_budget(two, reference_pages=4) == 2


def test_unreadable_pdf_does_not_raise(tmp_path: Path) -> None:
    """A pypdf failure must not throw away an otherwise valid render."""
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf")
    assert verify_page_budget(str(bad)) is None


def test_budget_can_be_disabled(tmp_path: Path) -> None:
    pdf = str(write_pdf(tmp_path / "long.pdf", 5))
    assert verify_page_budget(pdf, max_pages=None) == 5


def test_render_cv_rejects_an_over_budget_compile(tmp_path: Path) -> None:
    template_file = tmp_path / "template.tex"
    template_file.write_text(make_template())

    def fake_run(cmd, **kwargs):
        tex_path = next(a for a in cmd if a.endswith(".tex"))
        write_pdf(Path(tex_path.replace(".tex", ".pdf")), 3)
        return MagicMock(returncode=0, stderr="")

    with patch("nj.tailoring.renderer.subprocess.run", side_effect=fake_run):
        with pytest.raises(PageBudgetError):
            render_cv(
                cv_data=make_cv(),
                template_path=str(template_file),
                output_dir=str(tmp_path / "output"),
                company="Acme",
                job_title="ML Engineer",
            )


# --- escaping of dynamic strings ---


def test_soft_skills_are_escaped() -> None:
    cv = make_cv()
    cv["soft_skills"] = ["R&D leadership", "100% ownership"]
    filled = _fill_template(make_template(), cv)
    assert "R\\&D" in filled
    assert "100\\%" in filled
    assert "R&D leadership" not in filled


def test_unknown_skill_category_label_is_escaped() -> None:
    """Known labels are trusted LaTeX; a key out of the CV JSON is not."""
    out = _render_skills({"r&d_tools": ["Jira"]})
    assert "\\&" in out
    assert "R&D" not in out


def test_known_skill_labels_keep_their_intentional_latex() -> None:
    out = _render_skills({"cloud_devops": ["AWS"]})
    assert "Cloud \\& DevOps" in out


def test_safe_url_strips_latex_breakout_characters() -> None:
    """Escaping would break the link, so the defence is an allow-list."""
    assert _safe_url("github.com/user_name") == "github.com/user_name"
    assert "\\" not in _safe_url("github.com/x}\\input{/etc/passwd")
    assert "{" not in _safe_url("github.com/x}\\input{/etc/passwd")
    assert "}" not in _safe_url("github.com/x}\\input{/etc/passwd")
    assert _safe_url("") == ""
