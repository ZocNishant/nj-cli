from __future__ import annotations

PROMPT_VERSION = "cover_letter_v1"

SYSTEM_PROMPT = """You are an expert cover letter writer for ML and AI \
roles. You write concise, specific, non-generic cover letters that get \
read. You never use clichés like "I am passionate about" or "I would \
be a great fit". You write like a confident engineer, not a job seeker.

STRUCTURE — exactly 3 paragraphs:
Paragraph 1 (Opening): What specific thing about this role/company \
interests you. Reference something real from the JD. One concrete reason.

Paragraph 2 (Evidence): Your strongest relevant evidence. Lead with \
the anchor project for ML/CV roles. Connect your work directly to what \
they need. Specific numbers only.

Paragraph 3 (Closing): Brief. Work authorization status and availability. \
Enthusiasm without begging. One sentence on next steps.

RULES:
- Maximum 250 words total
- No bullet points
- Address to "Hiring Manager" if no name known
- Never mention the word "passionate"
- Only use facts from the candidate profile provided
- Sign off with the candidate's name from the profile"""


def _build_candidate_facts(cv_base: dict) -> str:
    facts = []
    personal = cv_base.get("personal", {})

    if personal.get("visa_note"):
        facts.append(personal["visa_note"])
    if personal.get("graduation_date"):
        edu = cv_base.get("education", [{}])[0]
        deg = edu.get("degree", "")
        inst = edu.get("institution", "")
        if deg and inst:
            facts.append(f"{deg} at {inst}, {personal['graduation_date']}")

    projects = cv_base.get("projects", [])
    anchor = next((p for p in projects if p.get("anchor")), None)
    if anchor:
        bullets = anchor.get("bullets", [])
        summary = bullets[0][:100] if bullets else ""
        facts.append(f"{anchor['name']}: {summary}")

    experience = cv_base.get("experience", [])
    incoming = [
        e for e in experience
        if isinstance(e, dict) and e.get("status") == "incoming"
    ]
    for exp in incoming[:1]:
        facts.append(
            f"Upcoming: {exp.get('title')} at "
            f"{exp.get('company')} ({exp.get('start')})"
        )

    skills = cv_base.get("skills", {})
    all_skills: list[str] = []
    for items in skills.values():
        if isinstance(items, list):
            all_skills.extend(items)
    if all_skills:
        facts.append(f"Core stack: {', '.join(all_skills[:8])}")

    return "\n".join(f"- {f}" for f in facts)


def build_user_prompt(
    job_title: str,
    job_company: str,
    job_description: str,
    matched_skills: list[str],
    overall_rationale: str,
    cv_base: dict | None = None,
) -> str:
    from nj.utils.text import truncate

    facts = _build_candidate_facts(cv_base) if cv_base else ""

    return f"""Write a cover letter for this application.

Role: {job_title} at {job_company}

Why this role fits (from scoring):
{overall_rationale}

Key matched skills: {", ".join(matched_skills[:6])}

JD excerpt:
{truncate(job_description, 800)}

Candidate facts to draw from:
{facts}

Write the 3-paragraph cover letter now. Plain text only, no formatting."""
