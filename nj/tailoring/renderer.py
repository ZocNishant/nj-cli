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


def render_cv(
    cv_data: dict,
    template_path: str,
    output_dir: str,
    company: str,
    job_title: str,
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
        logger.info("pdf_rendered", path=str(pdf_dst))
        return str(pdf_dst)


def _safe_filename(text: str) -> str:
    safe = re.sub(r"[^\w\-]", "_", text)
    return safe[:30].strip("_")


def _fill_template(template: str, cv: dict) -> str:
    personal = cv.get("personal", {})
    replacements = {
        "%%NAME%%": escape_latex(personal.get("name", "")),
        "%%LOCATION%%": escape_latex(personal.get("location", "")),
        "%%PHONE%%": escape_latex(personal.get("phone", "")),
        "%%EMAIL%%": escape_latex(personal.get("email", "")),
        "%%LINKEDIN%%": personal.get("linkedin", ""),
        "%%GITHUB%%": personal.get("github", ""),
        "%%SUMMARY_BLOCK%%": _render_summary(cv.get("summary", "")),
        "%%EDUCATION_BLOCK%%": _render_education(cv.get("education", [])),
        "%%SKILLS_BLOCK%%": _render_skills(cv.get("skills", {})),
        "%%EXPERIENCE_BLOCK%%": _render_experience(cv.get("experience", [])),
        "%%GAP_BLOCK%%": _render_gap(cv.get("gap_explanation")),
        "%%RESEARCH_INTERESTS%%": _render_research(cv.get("research_interests", [])),
        "%%PROJECTS_BLOCK%%": _render_projects(cv.get("projects", [])),
        "%%MEMBERSHIPS_BLOCK%%": _render_memberships(cv.get("memberships", [])),
        "%%CERTIFICATIONS_BLOCK%%": _render_certifications(
            cv.get("certifications", [])
        ),
        "%%SOFT_SKILLS%%": " $|$ ".join(cv.get("soft_skills", [])),
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
        else:
            continue
        lines.append(
            f"\\resumeSubheading\n"
            f"  {{{inst}}}{{{loc}}}\n"
            f"  {{{degree}}}{{{start} -- {end}}}"
        )
        if courses:
            lines.append("  \\resumeItemListStart")
            courses_str = escape_latex(", ".join(courses))
            lines.append(f"    \\resumeItem{{Relevant Courses: {courses_str}}}")
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
    }
    lines = []
    for key, items in skills.items():
        if not items:
            continue
        label = SKILL_LABELS.get(key, key.replace("_", " ").title())
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
            f"\\resumeSubheading\n"
            f"  {{{title}}}{{{start} -- {end}}}\n"
            f"  {{{company}}}{{{location}}}"
        )
        if status == "incoming":
            lines.append("  \\resumeItemListStart")
            lines.append("    \\resumeItem{\\textit{Incoming — starting June 2026}}")
            lines.append("  \\resumeItemListEnd")
        elif bullets:
            lines.append("  \\resumeItemListStart")
            for bullet in bullets:
                lines.append(f"    \\resumeItem{{{bullet}}}")
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
                lines.append(f"    \\resumeItem{{{bullet}}}")
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
