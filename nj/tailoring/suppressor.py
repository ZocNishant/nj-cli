from __future__ import annotations

import copy

from nj.models.job import Job
from nj.models.score import ScoreResult
from nj.utils.logger import get_logger

logger = get_logger(__name__)

ML_ROLE_TAGS = {"ml", "ai", "computer_vision", "deep_learning", "medical_imaging"}
SECURITY_SKILL_KEYS = {"security_tools"}
IT_ONLY_TAGS = {"it", "infrastructure", "networking"}
MAX_IT_BULLETS = 2


def suppress_for_role(
    cv: dict,
    job: Job,
    score: ScoreResult,
) -> dict:
    cv_copy = copy.deepcopy(cv)
    role_lower = job.title.lower()
    is_ml_role = any(
        kw in role_lower
        for kw in [
            "ml",
            "machine learning",
            "ai ",
            "artificial intelligence",
            "computer vision",
            "deep learning",
            "data scientist",
        ]
    )
    if not is_ml_role:
        return cv_copy

    skills = cv_copy.get("skills", {})
    for key in SECURITY_SKILL_KEYS:
        if key in skills:
            del skills[key]
            logger.debug("suppressed_skill_category", key=key, role=job.title)

    experience = cv_copy.get("experience", [])
    for exp in experience:
        if isinstance(exp, dict):
            tags = set(exp.get("tags", []))
        else:
            tags = set(exp.tags if hasattr(exp, "tags") else [])
        if tags and tags.issubset(IT_ONLY_TAGS) and not tags.intersection(ML_ROLE_TAGS):
            if isinstance(exp, dict):
                bullets = exp.get("bullets", [])
                if len(bullets) > MAX_IT_BULLETS:
                    exp["bullets"] = bullets[:MAX_IT_BULLETS]
            logger.debug(
                "compressed_it_experience",
                company=(
                    exp.get("company")
                    if isinstance(exp, dict)
                    else getattr(exp, "company", "")
                ),
            )

    return cv_copy
