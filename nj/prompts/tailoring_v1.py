from __future__ import annotations

PROMPT_VERSION = "tailoring_v1"

SYSTEM_PROMPT = """You are an expert CV writer for technical and professional \
roles. You tailor CVs to maximize interview conversion rates while \
maintaining complete factual accuracy.

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
- Reorder projects to lead with the anchor project for matching roles
- Suppress or compress less-relevant experience bullets (keep max 2)
- Remove unrelated tools from skills for focused roles
- Expand an existing bullet if the underlying fact supports it

ANCHOR PROJECT RULE:
The project marked anchor=true in the CV must always be listed first \
for roles matching its tags. Never move it lower. Never remove it.

INCOMING EXPERIENCE RULE:
For any experience entry with status='incoming': render as title + \
company + dates only. Do not invent responsibilities.
For status='active': include bullets if provided.

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

    anchor = next(
        (p for p in cv_base.get("projects", []) if p.get("anchor")),
        None,
    )
    anchor_note = ""
    if anchor:
        anchor_note = (
            f"\nIMPORTANT: '{anchor['name']}' is this candidate's "
            f"anchor project. Always list it first for relevant roles."
        )

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
{anchor_note}
BASE CV (tailor this — never invent content):
{json.dumps(cv_base, indent=2)[:3000]}

Return the tailored CV as JSON matching the base CV schema exactly.
Add a 3-line "summary" field targeting this specific role and company.
Remember: only rephrase and reorder. Never invent."""
