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
GastroVision for ML/CV roles. Add Moffitt internship if relevant. \
Connect your work directly to what they need. Specific numbers only.

Paragraph 3 (Closing): Brief. OPT status and availability. \
Enthusiasm without begging. One sentence on next steps.

RULES:
- Maximum 250 words total
- No bullet points
- Address to "Hiring Manager" if no name known
- Never mention the word "passionate"
- Only use facts from the candidate profile provided
- Sign off as: Nishant Joshi"""


def build_user_prompt(
    job_title: str,
    job_company: str,
    job_description: str,
    matched_skills: list[str],
    overall_rationale: str,
) -> str:
    from nj.utils.text import truncate

    return f"""Write a cover letter for this application.

Role: {job_title} at {job_company}

Why this role fits (from scoring):
{overall_rationale}

Key matched skills: {", ".join(matched_skills[:6])}

JD excerpt:
{truncate(job_description, 800)}

Candidate facts to draw from:
- GastroVision: 96.11% accuracy medical image classification, \
EfficientNet + ViT ensemble, Grad-CAM interpretability
- Incoming ML Intern at Moffitt Cancer Center (medical imaging, \
supervised by Dr. Palak Dave)
- MSCS at University of South Dakota, graduating December 2026
- F-1 OPT eligible December 2026
- Core stack: PyTorch, EfficientNet, ViT, OpenCV, Docker, FastAPI

Write the 3-paragraph cover letter now. Plain text only, no formatting."""
