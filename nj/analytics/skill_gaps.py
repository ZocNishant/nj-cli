from __future__ import annotations

from collections import Counter, defaultdict

from nj.models.score import ScoreResult
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class SkillGapReport:
    def __init__(
        self,
        gaps: list[dict],
        total_jobs_analyzed: int,
        avg_total_score: float,
        profile_coverage: float,
        matched_skill_frequency: list[dict],
    ):
        self.gaps = gaps
        self.total_jobs_analyzed = total_jobs_analyzed
        self.avg_total_score = avg_total_score
        self.profile_coverage = profile_coverage
        self.matched_skill_frequency = matched_skill_frequency


def analyze_skill_gaps(
    score_results: list[ScoreResult],
    top_n: int = 15,
) -> SkillGapReport:
    if not score_results:
        logger.warning("no_scores_for_gap_analysis")
        return SkillGapReport(
            gaps=[],
            total_jobs_analyzed=0,
            avg_total_score=0.0,
            profile_coverage=0.0,
            matched_skill_frequency=[],
        )

    total = len(score_results)
    avg_score = sum(r.total_score for r in score_results) / total

    missing_counter: Counter = Counter()
    missing_score_context: dict[str, list[int]] = defaultdict(list)
    matched_counter: Counter = Counter()

    for result in score_results:
        for skill in result.missing_skills:
            skill_clean = skill.strip().lower()
            if skill_clean and len(skill_clean) > 2:
                missing_counter[skill_clean] += 1
                missing_score_context[skill_clean].append(result.total_score)
        for skill in result.matched_skills:
            skill_clean = skill.strip().lower()
            if skill_clean:
                matched_counter[skill_clean] += 1

    gaps = []
    for skill, count in missing_counter.most_common(top_n * 2):
        frequency_pct = round((count / total) * 100)
        if frequency_pct < 10:
            continue

        scores_when_missing = missing_score_context[skill]
        avg_when_missing = (
            sum(scores_when_missing) / len(scores_when_missing)
            if scores_when_missing
            else avg_score
        )

        impact_score = frequency_pct * (avg_when_missing / 100)

        gaps.append(
            {
                "skill": skill,
                "frequency_pct": frequency_pct,
                "job_count": count,
                "avg_score_when_missing": round(avg_when_missing, 1),
                "impact_score": round(impact_score, 1),
                "estimated_score_boost": _estimate_boost(frequency_pct, skill),
            }
        )

    gaps.sort(key=lambda g: g["impact_score"], reverse=True)
    gaps = gaps[:top_n]

    total_skill_mentions = sum(matched_counter.values()) + sum(missing_counter.values())
    matched_mentions = sum(matched_counter.values())
    coverage = (matched_mentions / total_skill_mentions * 100) if total_skill_mentions > 0 else 0.0

    matched_freq = [
        {"skill": skill, "frequency_pct": round((count / total) * 100)}
        for skill, count in matched_counter.most_common(10)
        if round((count / total) * 100) >= 10
    ]

    logger.info(
        "skill_gap_analysis_complete",
        total_jobs=total,
        gaps_found=len(gaps),
        coverage=round(coverage, 1),
    )

    return SkillGapReport(
        gaps=gaps,
        total_jobs_analyzed=total,
        avg_total_score=round(avg_score, 1),
        profile_coverage=round(coverage, 1),
        matched_skill_frequency=matched_freq,
    )


def _estimate_boost(frequency_pct: int, skill: str) -> int:
    if frequency_pct >= 70:
        return 8
    elif frequency_pct >= 50:
        return 6
    elif frequency_pct >= 30:
        return 4
    else:
        return 2
