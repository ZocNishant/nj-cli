from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from nj.models.config import Config
from nj.models.job import Job
from nj.models.score import ScoreResult
from nj.prompts import prep_v1
from nj.providers.base import BaseLLMProvider, LLMRequest
from nj.tailoring.renderer import _safe_filename
from nj.utils.logger import get_logger
from nj.utils.text import escape_latex

logger = get_logger(__name__)


class PrepGenerationError(Exception):
    pass


async def generate_prep(
    job: Job,
    cv_base: dict,
    config: Config,
    provider: BaseLLMProvider,
    score: ScoreResult | None = None,
) -> dict:
    logger.info("prep_generation_start", job_id=job.id, company=job.company)

    score_dict = score.model_dump() if score else None
    user_prompt = prep_v1.build_user_prompt(
        job_title=job.title,
        job_company=job.company,
        job_description=job.description,
        cv_base=cv_base,
        score_result=score_dict,
    )
    request = LLMRequest(
        system=prep_v1.SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=4000,
        temperature=0.3,
        response_format="json",
    )

    for attempt in range(1, 3):
        try:
            response = await provider.complete(request)
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            data = json.loads(raw)
            logger.info(
                "prep_generation_complete",
                job_id=job.id,
                questions=len(data.get("technical_questions", [])),
            )
            return data
        except Exception as e:
            logger.warning("prep_generation_failed", attempt=attempt, error=str(e))
            if attempt == 2:
                raise PrepGenerationError(
                    f"Failed to generate prep after 2 attempts: {e}"
                )
    return {}


def render_prep_pdf(
    prep_data: dict,
    job: Job,
    cv_base: dict,
    output_dir: str,
) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    tex = _build_prep_latex(prep_data, job, cv_base)
    safe_company = _safe_filename(job.company)
    safe_title = _safe_filename(job.title)
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"nj_prep_{safe_company}_{safe_title}_{date_str}"

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / f"{filename}.tex"
        tex_path.write_text(tex, encoding="utf-8")
        result = subprocess.run(
            ["tectonic", "-X", "compile", str(tex_path)],
            capture_output=True,
            text=True,
            cwd=tmpdir,
        )
        if result.returncode != 0:
            logger.error("prep_tectonic_failed", stderr=result.stderr[:300])
            raise PrepGenerationError(f"PDF render failed: {result.stderr[:200]}")
        pdf_src = Path(tmpdir) / f"{filename}.pdf"
        if not pdf_src.exists():
            raise PrepGenerationError("PDF not found after compile")
        pdf_dst = Path(output_dir) / f"{filename}.pdf"
        shutil.copy2(pdf_src, pdf_dst)
        logger.info("prep_pdf_rendered", path=str(pdf_dst))
        return str(pdf_dst)


def _build_prep_latex(
    prep: dict,
    job: Job,
    cv_base: dict,
) -> str:
    personal = cv_base.get("personal", {})
    name = escape_latex(personal.get("name", "Candidate"))
    company = escape_latex(job.company)
    title = escape_latex(job.title)
    date = datetime.now(UTC).strftime("%B %d, %Y")

    brief = prep.get("company_brief", {})
    tech_qs = prep.get("technical_questions", [])
    behav_qs = prep.get("behavioural_questions", [])
    stories = prep.get("story_bank", [])
    quick = prep.get("quick_reference", {})

    lines = [
        r"\documentclass[letterpaper,11pt]{article}",
        r"\usepackage[empty]{fullpage}",
        r"\usepackage{titlesec}",
        r"\usepackage{enumitem}",
        r"\usepackage[hidelinks]{hyperref}",
        r"\usepackage[english]{babel}",
        r"\usepackage{xcolor}",
        r"\usepackage{tabularx}",
        r"\addtolength{\oddsidemargin}{-0.5in}",
        r"\addtolength{\evensidemargin}{-0.5in}",
        r"\addtolength{\textwidth}{1in}",
        r"\addtolength{\topmargin}{-.5in}",
        r"\addtolength{\textheight}{1.0in}",
        r"\titleformat{\section}{\vspace{-6pt}\scshape\raggedright\large}{}{0em}{}[\color{black}\titlerule\vspace{-4pt}]",
        r"\begin{document}",
        "",
        r"\begin{center}\textbf{\Huge \scshape Interview Prep}\\\vspace{4pt}",
        rf"\large {name} $\cdot$ {title} at {company}\\",
        rf"\small Prepared: {date}",
        r"\end{center}",
        "",
    ]

    # Company Brief
    lines += [r"\section{Company Brief}"]
    if brief.get("what_they_do"):
        lines += [
            r"\textbf{What they do:} " + escape_latex(brief["what_they_do"]) + r"\\[4pt]"
        ]
    if brief.get("why_hiring"):
        lines += [
            r"\textbf{Why hiring:} " + escape_latex(brief["why_hiring"]) + r"\\[4pt]"
        ]
    if brief.get("tech_stack_mentioned"):
        stack = ", ".join(brief["tech_stack_mentioned"])
        lines += [r"\textbf{Tech stack:} " + escape_latex(stack) + r"\\[4pt]"]
    lines += [""]

    # Quick Reference
    lines += [r"\section{Quick Reference}"]
    if quick.get("role_in_one_sentence"):
        lines += [
            r"\textbf{Role:} "
            + escape_latex(quick["role_in_one_sentence"])
            + r"\\[4pt]"
        ]
    if quick.get("top_3_they_want"):
        lines += [r"\textbf{They want:} \begin{itemize}[noitemsep,topsep=0pt]"]
        for w in quick["top_3_they_want"]:
            lines += [r"\item " + escape_latex(w)]
        lines += [r"\end{itemize}"]
    if quick.get("top_3_you_bring"):
        lines += [r"\textbf{You bring:} \begin{itemize}[noitemsep,topsep=0pt]"]
        for b in quick["top_3_you_bring"]:
            lines += [r"\item " + escape_latex(b)]
        lines += [r"\end{itemize}"]
    if quick.get("biggest_gap"):
        lines += [
            r"\textbf{Gap to address:} "
            + escape_latex(quick["biggest_gap"])
            + r"\\[2pt]"
        ]
    if quick.get("gap_framing"):
        lines += [
            r"\textbf{How to frame it:} "
            + escape_latex(quick["gap_framing"])
            + r"\\[4pt]"
        ]
    if quick.get("research_before_call"):
        lines += [
            r"\textbf{Research before call:} \begin{itemize}[noitemsep,topsep=0pt]"
        ]
        for r_ in quick["research_before_call"]:
            lines += [r"\item " + escape_latex(r_)]
        lines += [r"\end{itemize}"]
    lines += [""]

    # Technical Questions
    lines += [r"\section{Technical Questions}"]
    for i, q in enumerate(tech_qs, 1):
        conf = q.get("confidence", "medium")
        conf_color = (
            "green!60!black"
            if conf == "high"
            else "orange!80!black"
            if conf == "medium"
            else "red!70!black"
        )
        lines += [
            rf"\textbf{{{i}. {escape_latex(q.get('question', ''))}}}",
            rf"\textcolor{{{conf_color}}}{{\small [{conf}]}}\\[2pt]",
        ]
        if q.get("why_asked"):
            lines += [
                r"\textit{Why asked:} " + escape_latex(q["why_asked"]) + r"\\[2pt]"
            ]
        if q.get("your_answer"):
            lines += [
                r"\textit{Your answer:} "
                + escape_latex(q["your_answer"])
                + r"\\[6pt]"
            ]
    lines += [""]

    # Behavioural Questions
    lines += [r"\section{Behavioural Questions}"]
    for i, q in enumerate(behav_qs, 1):
        lines += [
            rf"\textbf{{{i}. {escape_latex(q.get('question', ''))}}}\\[2pt]"
        ]
        if q.get("situation"):
            lines += [
                r"\textit{Situation:} "
                + escape_latex(q["situation"])
                + r"\\[2pt]"
            ]
        if q.get("task"):
            lines += [
                r"\textit{Task:} " + escape_latex(q["task"]) + r"\\[2pt]"
            ]
        if q.get("talking_points"):
            lines += [r"\begin{itemize}[noitemsep,topsep=0pt]"]
            for pt in q["talking_points"]:
                lines += [r"\item " + escape_latex(pt)]
            lines += [r"\end{itemize}"]
        lines += [r"\\[4pt]"]
    lines += [""]

    # Story Bank
    lines += [r"\section{Story Bank}"]
    for story in stories:
        lines += [
            r"\textbf{" + escape_latex(story.get("story_title", "")) + r"}\\[2pt]"
        ]
        if story.get("opening_line"):
            lines += [
                r"\textit{Open with:} ``"
                + escape_latex(story["opening_line"])
                + r"''\\[2pt]"
            ]
        if story.get("jd_requirement_addressed"):
            lines += [
                r"\textit{Addresses:} "
                + escape_latex(story["jd_requirement_addressed"])
                + r"\\[2pt]"
            ]
        if story.get("key_metrics"):
            metrics = ", ".join(story["key_metrics"])
            lines += [
                r"\textit{Key metrics:} " + escape_latex(metrics) + r"\\[6pt]"
            ]

    lines += ["", r"\end{document}"]
    return "\n".join(lines)
