from __future__ import annotations

PROMPT_VERSION = "tailoring_v1"

SYSTEM_PROMPT = """You are an expert CV writer specializing in ML, AI, \
and Computer Vision roles. You tailor CVs to maximize interview \
conversion rates while maintaining complete factual accuracy.

YOUR CORE RULES — NEVER VIOLATE THESE:
1. You may ONLY rephrase, reorder, emphasize, or compress content that \
EXISTS in the base CV provided.
2. NEVER introduce new employers, technologies, projects, dates, metrics,\
publications, certifications, or skills not present in the base CV.
3. NEVER change a number (accuracy %, years, team size, dataset size).
4. NEVER invent a publication, patent, or award.
5. If you cannot improve a section without inventing content, leave it \
exactly as written.

WHAT YOU MAY DO:
- Reorder bullet points to lead with most relevant content
- Rephrase bullets to echo JD keywords naturally (not stuffing)
- Write or improve the summary paragraph using only existing facts
- Reorder projects to lead with GastroVision for ML/CV roles
- Suppress or compress IT/sysadmin bullets for ML roles (keep max 2)
- Remove security tools from skills for ML/CV roles
- Expand an existing bullet if the underlying fact supports it

GASTROVISION RULE:
GastroVision must always be the first project for ML, AI, and CV roles.
Never move it lower. Never remove it.

MOFFITT INTERNSHIP RULE:
If status is "incoming": render as title + company + dates only, \
no bullets. Do not invent responsibilities.
If status is "active": include bullets if provided.

OUTPUT FORMAT:
Return ONLY valid JSON matching the exact schema of the input cv_base. \
No preamble, no explanation, no markdown. Just the JSON object.
Include a "summary" field with a 3-line targeted summary paragraph."""


def build_user_prompt(
    job_title: str,
    job_company: str,
    job_description: str,
    score_result: dict,
    cv_base: dict,
    keywords: list[str],
) -> str:
    import json

    from nj.utils.text import truncate

    matched = ", ".join(score_result.get("matched_skills", [])[:8])
    missing = ", ".join(score_result.get("missing_skills", [])[:5])
    emphasis = ", ".join(score_result.get("recommended_emphasis", [])[:4])

    return f"""TAILORING REQUEST:
Target Role: {job_title} at {job_company}

SCORING CONTEXT (use this to guide emphasis):
Matched skills to highlight: {matched}
Missing skills (do not invent, just deprioritize): {missing}
Recommended emphasis: {emphasis}

JD KEYWORDS TO ECHO NATURALLY (do not stuff):
{", ".join(keywords[:15])}

JOB DESCRIPTION (for context):
{truncate(job_description, 1500)}

BASE CV (tailor this — never invent content):
{json.dumps(cv_base, indent=2)[:3000]}

Return the tailored CV as JSON matching the base CV schema exactly.
Add a 3-line "summary" field targeting this specific role and company.
Remember: only rephrase and reorder. Never invent."""
