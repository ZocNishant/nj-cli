from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from nj.utils.logger import get_logger
from nj.utils.text import escape_latex

logger = get_logger(__name__)


class RendererError(Exception):
    pass


class PageBudgetError(RendererError):
    """The compiled PDF ran past its page budget.

    Carries `pdf_path` because the file is deliberately left on disk: the
    operator needs to look at the overflow to decide what to cut.
    """

    def __init__(self, message: str, pdf_path: str, pages: int, max_pages: int):
        super().__init__(message)
        self.pdf_path = pdf_path
        self.pages = pages
        self.max_pages = max_pages


# A CV that spills onto a third page is a formatting failure, not a longer CV:
# the overflow is usually two orphan lines, and it reads as carelessness.
DEFAULT_MAX_PAGES = 2


def page_count(pdf_path: str) -> int | None:
    """Pages in a PDF, or None if it cannot be read.

    None is a real answer, not an error: a caller that cannot count pages must
    not conclude the document is within budget, and must not throw away an
    otherwise valid PDF either.
    """
    try:
        from pypdf import PdfReader

        return len(PdfReader(pdf_path).pages)
    except Exception as e:
        logger.warning("pdf_page_count_failed", path=pdf_path, error=str(e))
        return None


def verify_page_budget(
    pdf_path: str,
    max_pages: int | None = DEFAULT_MAX_PAGES,
    reference_pages: int | None = None,
) -> int | None:
    """Check a compiled PDF against its page budget.

    `reference_pages` is the base CV's own page count, when the caller knows it:
    tailoring reorders and compresses, so the tailored PDF should come out the
    same length as the base one. It tightens the budget but never loosens it —
    a base CV that is somehow four pages does not license a four-page tailored
    CV.

    Returns the page count (or None if unreadable). Raises PageBudgetError when
    the document is over budget.
    """
    pages = page_count(pdf_path)
    if pages is None or max_pages is None:
        return pages

    budget = max_pages
    if reference_pages is not None and 0 < reference_pages < budget:
        budget = reference_pages

    if pages > budget:
        logger.error("pdf_page_budget_exceeded", path=pdf_path, pages=pages, budget=budget)
        raise PageBudgetError(
            f"CV compiled to {pages} pages, budget is {budget}. "
            f"Orphan spillover reads as carelessness to a recruiter — cut a "
            f"bullet or tighten the summary. Overflowing PDF kept at {pdf_path}",
            pdf_path=pdf_path,
            pages=pages,
            max_pages=budget,
        )

    logger.info("pdf_page_budget_ok", path=pdf_path, pages=pages, budget=budget)
    return pages


def render_cv(
    cv_data: dict,
    template_path: str,
    output_dir: str,
    company: str,
    job_title: str,
    max_pages: int | None = DEFAULT_MAX_PAGES,
    reference_pages: int | None = None,
) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    template = Path(template_path).read_text(encoding="utf-8")
    filled = _fill_template(template, cv_data)
    safe_company = _safe_filename(company)
    safe_title = _safe_filename(job_title)
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"nj_{safe_company}_{safe_title}_{date_str}"
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / f"{filename}.tex"
        tex_path.write_text(filled, encoding="utf-8")
        logger.info("compiling_latex", tex=str(tex_path))
        result = subprocess.run(
            ["tectonic", "-X", "compile", str(tex_path)],
            capture_output=True,
            text=True,
            cwd=tmpdir,
        )
        if result.returncode != 0:
            logger.error("tectonic_failed", stderr=result.stderr[:500])
            raise RendererError(f"tectonic compilation failed:\n{result.stderr[:500]}")
        pdf_src = Path(tmpdir) / f"{filename}.pdf"
        if not pdf_src.exists():
            raise RendererError("tectonic ran but PDF not found")
        pdf_dst = Path(output_dir) / f"{filename}.pdf"
        shutil.copy2(pdf_src, pdf_dst)

        # Save tailored CV JSON for nj diff
        import json as _json

        json_dst = Path(output_dir) / f"{filename}.json"
        try:
            json_dst.write_text(
                _json.dumps(cv_data, indent=2),
                encoding="utf-8",
            )
            logger.debug("tailored_cv_json_saved", path=str(json_dst))
        except Exception as e:
            logger.warning("tailored_cv_json_save_failed", error=str(e))

        # Verified after the copy, so an over-budget PDF is still on disk for
        # the operator to inspect when this raises.
        verify_page_budget(str(pdf_dst), max_pages=max_pages, reference_pages=reference_pages)

        logger.info("pdf_rendered", path=str(pdf_dst))
        return str(pdf_dst)


def _safe_filename(text: str) -> str:
    safe = re.sub(r"[^\w\-]", "_", text)
    return safe[:30].strip("_")


# URLs land inside \href{...}, where escaping would corrupt the link but a stray
# brace or backslash would end the argument and start executing. Allow-list the
# characters a URL legitimately needs and drop the rest.
_URL_ALLOWED = re.compile(r"[^A-Za-z0-9\-._~:/?#\[\]@!$'()*+,;=%]")


def _safe_url(url: str) -> str:
    """Strip anything from a URL that could break out of \\href{...}.

    Escaping is not an option here — `\\_` inside an href is a broken link, not
    an escaped underscore — so the defence is an allow-list instead.
    """
    if not url:
        return ""
    return _URL_ALLOWED.sub("", str(url))


def _fill_template(template: str, cv: dict) -> str:
    personal = cv.get("personal", {})
    replacements = {
        "%%NAME%%": escape_latex(personal.get("name", "")),
        "%%LOCATION%%": escape_latex(personal.get("location", "")),
        "%%PHONE%%": escape_latex(personal.get("phone", "")),
        "%%EMAIL%%": escape_latex(personal.get("email", "")),
        "%%LINKEDIN%%": _safe_url(personal.get("linkedin", "")),
        "%%GITHUB%%": _safe_url(personal.get("github", "")),
        "%%SUMMARY_BLOCK%%": _render_summary(cv.get("summary", "")),
        "%%EDUCATION_BLOCK%%": _render_education(cv.get("education", [])),
        "%%SKILLS_BLOCK%%": _render_skills(cv.get("skills", {})),
        "%%EXPERIENCE_BLOCK%%": _render_experience(cv.get("experience", [])),
        "%%GAP_BLOCK%%": _render_gap(cv.get("gap_explanation")),
        "%%PROJECTS_BLOCK%%": _render_projects(cv.get("projects", [])),
        "%%RESEARCH_BLOCK%%": _section(
            "Research Interests",
            _render_research(cv.get("research_interests", [])),
            listed=False,
        ),
        "%%CERTIFICATIONS_BLOCK%%": _section(
            "Certifications", _render_certifications(cv.get("certifications", []))
        ),
        "%%MEMBERSHIPS_BLOCK%%": _section(
            "Professional Memberships", _render_memberships(cv.get("memberships", []))
        ),
        "%%SOFT_SKILLS_BLOCK%%": _section(
            "Soft Skills",
            " $|$ ".join(escape_latex(s) for s in cv.get("soft_skills", [])),
            listed=False,
        ),
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


def _render_summary(summary: str) -> str:
    if not summary or not summary.strip():
        return ""
    return (
        "\\section{Summary}\n"
        "\\begin{itemize}[leftmargin=0.15in, label={}]\n"
        "\\small{\\item{" + escape_latex(summary) + "}}\n"
        "\\end{itemize}\n"
    )


def _render_education(education: list) -> str:
    lines = []
    for edu in education:
        if isinstance(edu, dict):
            inst = escape_latex(edu.get("institution", ""))
            loc = escape_latex(edu.get("location", ""))
            degree = escape_latex(edu.get("degree", ""))
            start = escape_latex(edu.get("start", ""))
            end = escape_latex(edu.get("end", ""))
            courses = edu.get("courses", [])
            # Free-form lines under a degree — a thesis, a research project —
            # that are not courses and must not be folded into that list.
            highlights = edu.get("highlights", [])
        else:
            continue
        lines.append(
            f"\\resumeSubheading\n  {{{inst}}}{{{loc}}}\n  {{{degree}}}{{{start} -- {end}}}"
        )
        if courses or highlights:
            lines.append("  \\resumeItemListStart")
            if courses:
                courses_str = escape_latex(", ".join(courses))
                lines.append(f"    \\resumeItem{{Relevant Courses: {courses_str}}}")
            for highlight in highlights:
                lines.append(f"    \\resumeItem{{{escape_latex(str(highlight))}}}")
            lines.append("  \\resumeItemListEnd")
    return "\n".join(lines)


def _render_skills(skills: dict) -> str:
    SKILL_LABELS = {
        "programming_languages": "Programming Languages",
        "ml_frameworks": "ML/AI Frameworks",
        "deep_learning": "Deep Learning",
        "ml_techniques": "ML Techniques",
        "web_technologies": "Web Technologies",
        "databases": "Databases",
        "cloud_devops": "Cloud \\& DevOps",
        "security_tools": "Security Tools",
        "operating_systems": "Operating Systems",
        "it_network_tools": "IT \\& Network Tools",
        # An unregistered key still renders, as Title Case of the key itself,
        # so a missing entry here is a cosmetic bug rather than a crash:
        # "ml_statistical_techniques" would reach the PDF as "Ml Statistical
        # Techniques". These carry intentional `\&` and cannot be derived.
        "ml_models": "ML Models",
        "ml_statistical_techniques": "ML \\& Statistical Techniques",
        "deployment_mlops": "Deployment \\& MLOps",
        "bioinformatics_genomics": "Bioinformatics \\& Genomics",
        "systems_networking": "Systems \\& Networking",
        "tools": "Tools",
    }
    lines = []
    for key, items in skills.items():
        if not items:
            continue
        # Known labels are trusted LaTeX (they contain intentional `\&`). An
        # unknown key came from the CV JSON, so it is escaped like any other
        # dynamic string.
        label = SKILL_LABELS.get(key) or escape_latex(str(key).replace("_", " ").title())
        items_str = escape_latex(", ".join(items))
        lines.append(f"\\textbf{{{label}}}{{: {items_str}}} \\\\")
    return "\n".join(lines)


def _render_experience(experience: list) -> str:
    lines = []
    for exp in experience:
        if isinstance(exp, dict):
            title = escape_latex(exp.get("title", ""))
            company = escape_latex(exp.get("company", ""))
            location = escape_latex(exp.get("location", ""))
            start = escape_latex(exp.get("start", ""))
            end = escape_latex(exp.get("end", ""))
            status = exp.get("status", "ended")
            bullets = exp.get("bullets", [])
        else:
            title = escape_latex(getattr(exp, "title", ""))
            company = escape_latex(getattr(exp, "company", ""))
            location = escape_latex(getattr(exp, "location", ""))
            start = escape_latex(getattr(exp, "start", ""))
            end = escape_latex(getattr(exp, "end", ""))
            status = getattr(exp, "status", "ended")
            bullets = getattr(exp, "bullets", [])

        lines.append(
            f"\\resumeSubheading\n  {{{title}}}{{{start} -- {end}}}\n  {{{company}}}{{{location}}}"
        )
        if status == "incoming":
            lines.append("  \\resumeItemListStart")
            lines.append("    \\resumeItem{\\textit{Incoming — starting June 2026}}")
            lines.append("  \\resumeItemListEnd")
        elif bullets:
            lines.append("  \\resumeItemListStart")
            for bullet in bullets:
                lines.append(f"    \\resumeItem{{{escape_latex(bullet)}}}")
            lines.append("  \\resumeItemListEnd")
    return "\n".join(lines)


def _render_projects(projects: list) -> str:
    lines = []
    for proj in projects:
        if isinstance(proj, dict):
            name = escape_latex(proj.get("name", ""))
            tech = ", ".join(proj.get("tech", []))
            date = escape_latex(proj.get("date", ""))
            bullets = proj.get("bullets", [])
        else:
            continue
        tech_escaped = escape_latex(tech)
        lines.append(
            f"\\resumeProjectHeading\n"
            f"  {{\\textbf{{{name}}} $|$ \\emph{{{tech_escaped}}}}}{{{date}}}"
        )
        if bullets:
            lines.append("  \\resumeItemListStart")
            for bullet in bullets:
                lines.append(f"    \\resumeItem{{{escape_latex(bullet)}}}")
            lines.append("  \\resumeItemListEnd")
    return "\n".join(lines)


def _render_gap(gap: dict | None) -> str:
    if not gap:
        return ""
    period = escape_latex(gap.get("period", ""))
    reason = escape_latex(gap.get("reason", ""))
    return (
        "\\section{Employment \\& Education Gap Explanation}\n"
        "\\resumeSubHeadingListStart\n"
        f"\\resumeItem{{\\textbf{{{period}:}} {reason}}}\n"
        "\\resumeSubHeadingListEnd\n"
    )


def _render_research(interests: list) -> str:
    return " $|$ ".join(escape_latex(i) for i in interests)


def _section(title: str, body: str, *, listed: bool = True) -> str:
    """A whole section, or nothing at all when the body is empty.

    Sections must own their headings. When the template carried the `\\section`
    itself, a CV with no research interests still printed the heading and its
    rule with a blank space beneath — the reader sees a broken document, not an
    omitted section.
    """
    if not body or not body.strip():
        return ""
    if listed:
        return f"\\section{{{title}}}\n\\resumeSubHeadingListStart\n{body}\n\\resumeSubHeadingListEnd\n"
    return f"\\section{{{title}}}\n\\small {body}\n\\vspace{{2pt}}\n"


def _render_memberships(memberships: list) -> str:
    lines = []
    for m in memberships:
        if isinstance(m, dict):
            name = escape_latex(m.get("name", ""))
            detail = escape_latex(m.get("detail", ""))
            lines.append(f"\\resumeItem{{\\textbf{{{name}}} -- {detail}}}")
    return "\n".join(lines)


def _render_certifications(certs: list) -> str:
    lines = []
    for c in certs:
        if isinstance(c, dict):
            name = escape_latex(c.get("name", ""))
            detail = escape_latex(c.get("detail", ""))
            date = escape_latex(c.get("date", ""))
            date_str = f" ({date})" if date else ""
            lines.append(f"\\resumeItem{{\\textbf{{{name}}} -- {detail}{date_str}}}")
    return "\n".join(lines)
