from __future__ import annotations

PROMPT_VERSION = "intern_update_v1"

SYSTEM_PROMPT = """You convert plain English internship descriptions into \
professional CV bullet points. You write strong, metric-driven bullets \
using action verbs. You never invent metrics not mentioned by the user.
Return ONLY a JSON array of strings. No preamble, no explanation."""


def build_user_prompt(description: str) -> str:
    return f"""Convert this internship description into 3-4 CV bullet \
points for the role: Machine Learning Intern at Moffitt Cancer Center.

The user's description:
{description}

Rules:
- Start each bullet with a strong action verb
- Include specific metrics only if the user mentioned them
- Keep each bullet under 20 words
- Make them ATS-friendly for ML/Computer Vision roles
- Do not invent any technology, result, or responsibility

Return ONLY a JSON array of strings like:
["Bullet one text.", "Bullet two text.", "Bullet three text."]"""
