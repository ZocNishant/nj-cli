from __future__ import annotations

PROMPT_VERSION = "scoring_v1"

SYSTEM_PROMPT = """You are an expert technical recruiter evaluating \
candidate fit for a specific job opening.

Your job is to score the fit between a candidate profile and a job \
description across 6 categories. Think step by step before assigning \
any score.

SCORING CATEGORIES AND WEIGHTS:
- skills_match (30%): How well do the candidate's technical skills match \
the JD requirements? Look at exact matches, related skills, and depth.
- experience_relevance (25%): How relevant is the candidate's work history \
and projects to this role? Weight ML/CV projects heavily.
- role_alignment (20%): Does the job title and scope match the candidate's \
target roles and career trajectory? Use the strict rules below.
- sponsorship_compatibility (15%): Based on visa keywords in the JD, how \
compatible is this role for the candidate's visa/work authorization status?
- location_fit (5%): Does the job location work for the candidate \
(USA preferred, remote acceptable, international possible)?
- resume_strength (5%): How strong is the candidate's overall profile \
presentation for this specific role?

ROLE_ALIGNMENT STRICT SCORING RULES:
- Target roles are listed in the CANDIDATE CONTEXT section below.
- Job title clearly in the candidate's target role family → 70-100
- Adjacent or related role (e.g. Data Scientist for ML Engineer) → 40-69
- Tangentially related role (e.g. Backend Eng for ML candidate) → 25-39
- Unrelated role (e.g. DevOps/Infrastructure for ML candidate) → 0-25
- STRICT: DevOps, SRE, Platform, or Infrastructure role for an ML/AI \
candidate → 0-20
- STRICT: Marketing, Sales, Growth, or non-technical role for any \
engineering candidate → 0-15
- STRICT: Intern, Werkstudent, or Apprentice role for a mid-level or \
senior candidate → 0-20

SCORE CAP RULE (MANDATORY):
If role_alignment score is below 30, the total_score MUST NOT exceed 50, \
regardless of skills_match or experience_relevance scores. \
A strong ML engineer is not a good fit for a DevOps role even if they \
know Linux. Enforce this cap strictly before returning your JSON.

ANTI-HALLUCINATION RULE:
Only score based on what is explicitly present in the candidate profile \
provided. Do not assume skills or experience not listed.

CONFIDENCE SCORE:
Rate your confidence in this scoring 0.0-1.0 based on how clearly the \
JD and profile allow comparison. Low confidence = vague JD or unusual role.

OUTPUT FORMAT:
Return ONLY valid JSON matching this exact schema. No preamble, no \
explanation, no markdown. Just the JSON object:
{
  "total_score": <weighted average integer 0-100>,
  "confidence": <float 0.0-1.0>,
  "sub_scores": [
    {
      "category": "<category_name>",
      "score": <integer 0-100>,
      "weight": <float>,
      "rationale": "<one sentence explaining this score>",
      "evidence": ["<phrase from JD that drove this score>"]
    }
  ],
  "matched_skills": ["<skill present in both profile and JD>"],
  "missing_skills": ["<skill in JD not present in profile>"],
  "recommended_emphasis": ["<what to lead with in tailored CV>"],
  "visa_compatible": <true/false>,
  "visa_notes": "<one sentence about visa compatibility>",
  "overall_rationale": "<2-3 sentences summarizing the fit>"
}

Include all 6 categories in sub_scores. Use exact category name strings:
skills_match, experience_relevance, role_alignment, \
sponsorship_compatibility, location_fit, resume_strength"""


def _build_candidate_context(
    cv_base: dict, target_roles: list[str] | None = None
) -> str:
    personal = cv_base.get("personal", {})
    name = personal.get("name", "Candidate")
    visa_status = personal.get("visa_status", "")
    work_auth = personal.get("work_authorization", "")
    grad_date = personal.get("graduation_date", "")
    seniority = cv_base.get("seniority", "")

    projects = cv_base.get("projects", [])
    anchor = next(
        (p for p in projects if p.get("anchor")),
        projects[0] if projects else {},
    )
    anchor_name = anchor.get("name", "")
    anchor_bullets = anchor.get("bullets", [])
    anchor_summary = anchor_bullets[0][:120] if anchor_bullets else ""

    skills = cv_base.get("skills", {})
    all_skills: list[str] = []
    for items in skills.values():
        if isinstance(items, list):
            all_skills.extend(items[:3])
    top_skills = ", ".join(all_skills[:10])

    context = f"CANDIDATE: {name}\n"
    if seniority:
        context += f"Seniority: {seniority}\n"
    _no_sponsorship_needed = visa_status in (
        "citizen",
        "permanent_resident",
        "not_applicable",
    )
    if work_auth and not _no_sponsorship_needed:
        context += f"Work auth: {work_auth}\n"
    if grad_date:
        context += f"Graduation: {grad_date}\n"
    effective_roles = target_roles or cv_base.get("target_roles", [])
    if effective_roles:
        context += f"Target roles: {', '.join(effective_roles)}\n"
    if anchor_name:
        context += f"Strongest project: {anchor_name}"
        if anchor_summary:
            context += f" — {anchor_summary}"
        context += "\n"
    context += f"Core skills: {top_skills}\n"
    return context


def build_user_prompt(
    job_title: str,
    job_description: str,
    skills: dict | list,
    top_projects: list[dict],
    weights: dict[str, float] | None = None,
    cv_base: dict | None = None,
    target_roles: list[str] | None = None,
) -> str:
    from nj.utils.text import truncate

    weights = weights or {
        "skills_match": 0.30,
        "experience_relevance": 0.25,
        "role_alignment": 0.20,
        "sponsorship_compatibility": 0.15,
        "location_fit": 0.05,
        "resume_strength": 0.05,
    }

    candidate_context = (
        _build_candidate_context(cv_base, target_roles) if cv_base else ""
    )

    profile_sections = []

    if isinstance(skills, list):
        skills_str = ", ".join(skills)
    else:
        flat: list[str] = []
        for items in skills.values():
            if isinstance(items, list):
                flat.extend(items)
        skills_str = ", ".join(flat)
    profile_sections.append(f"SKILLS:\n{skills_str}")

    if cv_base:
        experience = cv_base.get("experience", [])
        if experience:
            exp_lines = []
            for exp in experience:
                if isinstance(exp, dict):
                    title = exp.get("title", "")
                    company = exp.get("company", "")
                    start = exp.get("start", "")
                    end = exp.get("end", "")
                    bullets = exp.get("bullets", [])[:2]
                    exp_lines.append(f"  {title} @ {company} ({start}–{end})")
                    for b in bullets:
                        exp_lines.append(f"    • {str(b)[:100]}")
            profile_sections.append("WORK EXPERIENCE:\n" + "\n".join(exp_lines))

    if top_projects:
        proj_lines = []
        for p in top_projects:
            name = p.get("name", "")
            tech = ", ".join(p.get("tech", []))
            bullets = p.get("bullets", [])
            anchor = " [ANCHOR]" if p.get("anchor") else ""
            proj_lines.append(f"  {name}{anchor} | {tech}")
            if bullets:
                proj_lines.append(f"    • {str(bullets[0])[:120]}")
        profile_sections.append("PROJECTS:\n" + "\n".join(proj_lines))

    if cv_base:
        education = cv_base.get("education", [])
        if education:
            edu_lines = []
            for edu in education:
                if isinstance(edu, dict):
                    degree = edu.get("degree", "")
                    inst = edu.get("institution", "")
                    end = edu.get("end", "")
                    courses = edu.get("courses", [])[:4]
                    edu_lines.append(f"  {degree} — {inst} ({end})")
                    if courses:
                        edu_lines.append(f"    Courses: {', '.join(courses)}")
            profile_sections.append("EDUCATION:\n" + "\n".join(edu_lines))

    if cv_base:
        interests = cv_base.get("research_interests", [])
        if interests:
            profile_sections.append("RESEARCH INTERESTS:\n  " + ", ".join(interests))

    full_profile = "\n\n".join(profile_sections)

    return f"""CANDIDATE CONTEXT:
{candidate_context}

FULL CANDIDATE PROFILE:
{full_profile}

SCORING WEIGHTS TO APPLY:
{chr(10).join(f"  {k}: {v}" for k, v in weights.items())}

JOB TO EVALUATE:
Title: {job_title}

Description:
{truncate(job_description, 2000)}

Score this candidate holistically for this specific job.
Consider ALL sections of the profile — not just skills.
Weight work experience and projects heavily for relevance.
Return only JSON."""
