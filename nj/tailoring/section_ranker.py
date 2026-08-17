from __future__ import annotations

from nj.models.score import ScoreResult
from nj.utils.logger import get_logger

logger = get_logger(__name__)


def rank_projects(
    projects: list[dict],
    score: ScoreResult,
) -> list[dict]:
    if not projects:
        return projects

    anchor = None
    rest = []
    for p in projects:
        if p.get("anchor") is True:
            anchor = p
        else:
            rest.append(p)

    emphasis_lower = [e.lower() for e in score.recommended_emphasis]
    matched_lower = [s.lower() for s in score.matched_skills]
    relevant_terms = emphasis_lower + matched_lower

    def relevance_score(project: dict) -> int:
        tags = [t.lower() for t in project.get("tags", [])]
        tech = [t.lower() for t in project.get("tech", [])]
        name = project.get("name", "").lower()
        score_val = 0
        for term in relevant_terms:
            if any(term in t for t in tags + tech) or term in name:
                score_val += 1
        return -score_val

    rest_sorted = sorted(rest, key=relevance_score)
    result = []
    if anchor:
        result.append(anchor)
    result.extend(rest_sorted)

    logger.debug("projects_ranked", order=[p.get("name", "") for p in result])
    return result
