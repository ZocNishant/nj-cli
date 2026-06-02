from __future__ import annotations

PROMPT_VERSION = "role_update_v1"

SYSTEM_PROMPT = """You convert plain English role descriptions into \
professional CV bullet points. You write strong, metric-driven bullets \
using action verbs. You never invent metrics not mentioned by the user.
Return ONLY a JSON array of strings. No preamble, no explanation."""


def build_user_prompt(description: str, title: str = "", company: str = "") -> str:
    role_context = ""
    if title:
        role_context = f" for the role: {title}"
        if company:
            role_context += f" at {company}"

    return f"""Convert this work description into 3-4 CV bullet points{role_context}.

The user's description:
{description}

Rules:
- Start each bullet with a strong action verb
- Include specific metrics only if the user mentioned them
- Keep each bullet under 20 words
- Make them ATS-friendly
- Do not invent any technology, result, or responsibility

Return ONLY a JSON array of strings like:
["Bullet one text.", "Bullet two text.", "Bullet three text."]"""
