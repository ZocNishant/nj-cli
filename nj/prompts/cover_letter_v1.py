from __future__ import annotations

from nj.prompts.untrusted import UNTRUSTED_INPUT_NOTICE

PROMPT_VERSION = "cover_letter_v1"

SYSTEM_PROMPT = """You are an expert cover letter writer for technical and \
professional roles. You write concise, specific, non-generic cover letters \
that get read. You never use clichés like "I am passionate about" or "I \
would be a great fit". You write like a confident professional, not a job seeker.

STRUCTURE — exactly 3 paragraphs:
Paragraph 1 (Opening): What specific thing about this role/company \
interests you. Reference something real from the JD. One concrete reason.

Paragraph 2 (Evidence): Your strongest relevant evidence. Lead with \
the anchor project for matching roles. Connect your work directly to what \
they need. Specific numbers only.

Paragraph 3 (Closing): Brief. Work authorization status (if applicable) \
and availability. Enthusiasm without begging. One sentence on next steps.

RULES:
- Maximum 250 words total
- No bullet points
- Open with "Dear <name>," or "Dear Hiring Manager," if no name is known
- Close with "Sincerely," then the candidate's name

LAYOUT — plain text, not prose run together:
Greeting on its own line, blank line, then each paragraph separated by a blank
line, then a blank line, "Sincerely,", and the name on the final line.
- Never mention the word "passionate"
- Only use facts from the candidate profile provided
- Sign off with the candidate's name from the profile"""


# This prompt receives a scraped job posting, so it carries the shared
# instruction for handling text inside <job_description> tags.
SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\n" + UNTRUSTED_INPUT_NOTICE


def _build_candidate_facts(cv_base: dict) -> str:
    facts = []
    personal = cv_base.get("personal", {})

    # First, because the system prompt instructs the model to sign off with it.
    # Omitting it did not produce an unsigned letter — it produced one signed
    # "[Candidate Name]", which reads as a mail merge that failed.
    if personal.get("name"):
        facts.append(f"Candidate name (sign the letter with this): {personal['name']}")

    visa_status = personal.get("visa_status", "")
    work_auth = personal.get("work_authorization", "")
    _no_sponsorship_needed = visa_status in ("citizen", "permanent_resident", "not_applicable")
    if work_auth and not _no_sponsorship_needed:
        facts.append(work_auth)
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

    # Most recent roles first, whatever their status. This used to select only
    # `status == "incoming"`, so the day an internship finished it vanished from
    # every cover letter — the candidate's only professional experience, dropped
    # by the field that was supposed to highlight it.
    experience = [e for e in cv_base.get("experience", []) if isinstance(e, dict)]
    for exp in experience[:2]:
        when = (
            f"starting {exp.get('start')}"
            if exp.get("status") == "incoming"
            else f"{exp.get('start')} to {exp.get('end')}"
        )
        line = f"{exp.get('title')} at {exp.get('company')} ({when})"
        bullets = exp.get("bullets") or []
        if bullets:
            line += f" -- {bullets[0][:220]}"
        facts.append(line)

    skills = cv_base.get("skills", {})
    all_skills: list[str] = []
    for items in skills.values():
        if isinstance(items, list):
            all_skills.extend(items)
    if all_skills:
        facts.append(f"Core stack: {', '.join(all_skills[:8])}")

    return "\n".join(f"- {f}" for f in facts)


def build_system_prompt(cv_base: dict | None = None) -> str:
    """The instructions plus the candidate's facts — the operator-authored turn.

    Same split as `tailoring_v1.build_system_prompt`: the candidate's facts are
    the operator's, the job posting is not, and they belong in different turns.
    A cover letter is signed by the candidate and read by a human, so a fact the
    posting managed to inject here is a lie the candidate has put their name to.
    """
    if not cv_base:
        return SYSTEM_PROMPT

    facts = _build_candidate_facts(cv_base)
    if not facts:
        return SYSTEM_PROMPT

    return (
        SYSTEM_PROMPT
        + "\n\nCANDIDATE FACTS — the only facts you may assert about this "
        + "person. Do not add to them.\n"
        + facts
    )


def build_user_prompt(
    job_title: str,
    job_company: str,
    job_description: str,
    matched_skills: list[str],
    overall_rationale: str,
    cv_base: dict | None = None,
) -> str:
    """The task and the untrusted posting. Deliberately carries no CV content.

    `cv_base` is accepted and ignored so existing call sites keep working; the
    candidate's facts belong in `build_system_prompt`.
    """
    del cv_base

    from nj.prompts.untrusted import fence

    return f"""Write a cover letter for this application.

Role: {job_title} at {job_company}

Why this role fits (from scoring):
{overall_rationale}

Key matched skills: {", ".join(matched_skills[:6])}

JD excerpt (untrusted):
{fence(job_description, 800)}

Draw only on the candidate facts given in your system prompt.
Write the 3-paragraph cover letter now. Plain text only, no formatting."""
