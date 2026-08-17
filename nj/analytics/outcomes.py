from __future__ import annotations

from nj.models.application import ApplicationRecord, OutcomeType
from nj.models.score import ScoreResult
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class OutcomeReport:
    def __init__(
        self,
        total_with_outcomes: int,
        interview_rate_by_score_band: dict[str, float],
        optimal_threshold: int | None,
        score_outcome_pairs: list[dict],
        avg_score_interviews: float,
        avg_score_rejections: float,
        recommendation: str,
    ):
        self.total_with_outcomes = total_with_outcomes
        self.interview_rate_by_score_band = interview_rate_by_score_band
        self.optimal_threshold = optimal_threshold
        self.score_outcome_pairs = score_outcome_pairs
        self.avg_score_interviews = avg_score_interviews
        self.avg_score_rejections = avg_score_rejections
        self.recommendation = recommendation


def analyze_outcomes(
    applications: list[ApplicationRecord],
    score_results: dict[str, ScoreResult],
) -> OutcomeReport:
    with_outcomes = [a for a in applications if a.outcome is not None]
    if not with_outcomes:
        return OutcomeReport(
            total_with_outcomes=0,
            interview_rate_by_score_band={},
            optimal_threshold=None,
            score_outcome_pairs=[],
            avg_score_interviews=0.0,
            avg_score_rejections=0.0,
            recommendation=(
                "No outcome data yet. Run nj watch after applying to collect callbacks."
            ),
        )

    pairs = []
    for app in with_outcomes:
        score = score_results.get(app.job_id)
        if score:
            pairs.append(
                {
                    "score": score.total_score,
                    "outcome": app.outcome.value,
                    "company": app.job_id,
                }
            )

    if not pairs:
        return OutcomeReport(
            total_with_outcomes=len(with_outcomes),
            interview_rate_by_score_band={},
            optimal_threshold=None,
            score_outcome_pairs=[],
            avg_score_interviews=0.0,
            avg_score_rejections=0.0,
            recommendation="Scores not found for applications with outcomes.",
        )

    bands: dict[str, list[str]] = {
        "50-59": [],
        "60-69": [],
        "70-79": [],
        "80-89": [],
        "90-100": [],
    }
    for pair in pairs:
        s = pair["score"]
        if 50 <= s <= 59:
            bands["50-59"].append(pair["outcome"])
        elif 60 <= s <= 69:
            bands["60-69"].append(pair["outcome"])
        elif 70 <= s <= 79:
            bands["70-79"].append(pair["outcome"])
        elif 80 <= s <= 89:
            bands["80-89"].append(pair["outcome"])
        elif s >= 90:
            bands["90-100"].append(pair["outcome"])

    interview_outcomes = {OutcomeType.INTERVIEW.value, OutcomeType.OFFER.value}
    rate_by_band: dict[str, float] = {}
    for band, outcomes in bands.items():
        if outcomes:
            interviews = sum(1 for o in outcomes if o in interview_outcomes)
            rate_by_band[band] = round(interviews / len(outcomes) * 100, 1)

    interview_scores = [p["score"] for p in pairs if p["outcome"] in interview_outcomes]
    rejection_scores = [p["score"] for p in pairs if p["outcome"] == OutcomeType.REJECTION.value]
    avg_interviews = sum(interview_scores) / len(interview_scores) if interview_scores else 0.0
    avg_rejections = sum(rejection_scores) / len(rejection_scores) if rejection_scores else 0.0

    optimal = None
    band_order = ["50-59", "60-69", "70-79", "80-89", "90-100"]
    for band in band_order:
        rate = rate_by_band.get(band, 0)
        if rate >= 25:
            optimal = int(band.split("-")[0])
            break

    if optimal and avg_interviews > 0:
        recommendation = (
            f"Based on {len(pairs)} data points: "
            f"jobs scoring {optimal}+ have "
            f"{rate_by_band.get(f'{optimal}-{optimal + 9}', 0)}%+ "
            f"interview rate. "
            f"Suggested threshold: {optimal}."
        )
    elif len(pairs) < 10:
        recommendation = (
            f"Only {len(pairs)} data points — "
            f"need 10+ to recommend a threshold. "
            f"Keep applying and checking nj watch."
        )
    else:
        recommendation = "Insufficient interview callbacks to identify optimal threshold yet."

    logger.info(
        "outcome_analysis_complete",
        total=len(pairs),
        avg_interviews=round(avg_interviews, 1),
        avg_rejections=round(avg_rejections, 1),
        optimal_threshold=optimal,
    )

    return OutcomeReport(
        total_with_outcomes=len(with_outcomes),
        interview_rate_by_score_band=rate_by_band,
        optimal_threshold=optimal,
        score_outcome_pairs=pairs,
        avg_score_interviews=round(avg_interviews, 1),
        avg_score_rejections=round(avg_rejections, 1),
        recommendation=recommendation,
    )
