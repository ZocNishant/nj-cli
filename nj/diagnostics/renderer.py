from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from nj.models.diagnosis import DiagnosisResult, HealthLevel, Severity
from nj.tailoring.renderer import _safe_filename
from nj.utils.logger import get_logger
from nj.utils.text import escape_latex

logger = get_logger(__name__)

SEVERITY_COLORS = {
    Severity.HIGH: "red!70!black",
    Severity.MEDIUM: "orange!80!black",
    Severity.LOW: "blue!60!black",
}

HEALTH_COLORS = {
    HealthLevel.WEAK: "red!70!black",
    HealthLevel.MODERATE: "orange!80!black",
    HealthLevel.STRONG: "green!60!black",
}


def render_diagnosis_pdf(
    result: DiagnosisResult,
    cv_base: dict,
    output_dir: str,
) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    personal = cv_base.get("personal", {})
    name = personal.get("name", "Candidate")
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"nj_diagnosis_{_safe_filename(name)}_{date_str}"
    tex = _build_diagnosis_latex(result, cv_base)

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / f"{filename}.tex"
        tex_path.write_text(tex, encoding="utf-8")
        proc = subprocess.run(
            ["tectonic", "-X", "compile", str(tex_path)],
            capture_output=True,
            text=True,
            cwd=tmpdir,
        )
        if proc.returncode != 0:
            logger.error("diagnosis_pdf_failed", stderr=proc.stderr[:300])
            raise RuntimeError(f"PDF render failed: {proc.stderr[:200]}")
        pdf_src = Path(tmpdir) / f"{filename}.pdf"
        pdf_dst = Path(output_dir) / f"{filename}.pdf"
        shutil.copy2(pdf_src, pdf_dst)
        logger.info("diagnosis_pdf_rendered", path=str(pdf_dst))
        return str(pdf_dst)


def _build_diagnosis_latex(result: DiagnosisResult, cv_base: dict) -> str:
    personal = cv_base.get("personal", {})
    name = escape_latex(personal.get("name", "Candidate"))
    date = datetime.now(UTC).strftime("%B %d, %Y")
    health_color = HEALTH_COLORS[result.overall_health]

    lines = [
        r"\documentclass[letterpaper,11pt]{article}",
        r"\usepackage[empty]{fullpage}",
        r"\usepackage{titlesec}",
        r"\usepackage{enumitem}",
        r"\usepackage[hidelinks]{hyperref}",
        r"\usepackage[english]{babel}",
        r"\usepackage{xcolor}",
        r"\usepackage{mdframed}",
        r"\addtolength{\oddsidemargin}{-0.5in}",
        r"\addtolength{\evensidemargin}{-0.5in}",
        r"\addtolength{\textwidth}{1in}",
        r"\addtolength{\topmargin}{-.5in}",
        r"\addtolength{\textheight}{1.0in}",
        r"\titleformat{\section}{\vspace{-6pt}\scshape\raggedright\large}{}{0em}{}[\color{black}\titlerule\vspace{-4pt}]",
        r"\begin{document}",
        "",
        rf"\begin{{center}}\textbf{{\Huge \scshape CV Diagnosis}}\\\vspace{{4pt}}",
        rf"\large {name} $\cdot$ \textcolor{{{health_color}}}{{\textbf{{{result.overall_health.value.upper()}}}}}\\",
        rf"\small Generated: {date}",
        r"\end{center}",
        "",
    ]

    if result.top_recommendation:
        lines += [
            r"\begin{mdframed}[backgroundcolor=yellow!15,linecolor=orange]",
            r"\textbf{Top recommendation:} " + escape_latex(result.top_recommendation),
            r"\end{mdframed}",
            "",
        ]

    if result.recruiter_first_impression:
        lines += [
            r"\section{Recruiter First Impression (15 seconds)}",
            r"\textit{" + escape_latex(result.recruiter_first_impression) + r"}",
            "",
        ]

    if result.positioning_mismatch:
        lines += [
            r"\section{Positioning Analysis}",
            escape_latex(result.positioning_mismatch),
            "",
        ]

    if result.critical_issues:
        lines += [r"\section{Critical Issues}"]
        for issue in result.critical_issues:
            color = SEVERITY_COLORS[issue.severity]
            lines += [
                rf"\textcolor{{{color}}}{{\textbf{{[{issue.severity.value.upper()}] {escape_latex(issue.section)}}}}}\\[2pt]",
                r"\textbf{Issue:} " + escape_latex(issue.issue) + r"\\[2pt]",
                r"\textbf{Fix:} " + escape_latex(issue.fix) + r"\\[8pt]",
            ]
        lines += [""]

    if result.hidden_strengths:
        lines += [
            r"\section{Hidden Strengths (You Are Underselling These)}",
            r"\begin{itemize}[noitemsep,topsep=2pt]",
        ]
        for s in result.hidden_strengths:
            lines += [r"\item " + escape_latex(s)]
        lines += [r"\end{itemize}", ""]

    if result.strong_sections or result.weak_sections:
        lines += [r"\section{Section Assessment}"]
        if result.strong_sections:
            strong = ", ".join(result.strong_sections)
            lines += [
                r"\textbf{\textcolor{green!60!black}{Strong:}} "
                + escape_latex(strong)
                + r"\\[4pt]"
            ]
        if result.weak_sections:
            weak = ", ".join(result.weak_sections)
            lines += [
                r"\textbf{\textcolor{red!70!black}{Needs work:}} "
                + escape_latex(weak)
                + r"\\[4pt]"
            ]
        lines += [""]

    if result.ats_concerns:
        lines += [
            r"\section{ATS Concerns}",
            r"\begin{itemize}[noitemsep,topsep=2pt]",
        ]
        for c in result.ats_concerns:
            lines += [r"\item " + escape_latex(c)]
        lines += [r"\end{itemize}", ""]

    if result.score_pattern_analysis:
        lines += [
            r"\section{Score Pattern Analysis}",
            escape_latex(result.score_pattern_analysis),
            "",
        ]

    lines += [r"\end{document}"]
    return "\n".join(lines)
