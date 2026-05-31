"""
Application postmortem analysis.
Detects failure patterns across rejections and no-responses.
Answers: why are applications not converting?
"""
from __future__ import annotations

from collections import defaultdict, Counter

from nj.models.application import ApplicationRecord, OutcomeType
from nj.models.score import ScoreResult
from nj.models.job import Job
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class PostmortemReport:
    def __init__(self):
        self.total_applications = 0
        self.total_with_outcomes = 0
        self.interview_rate = 0.0
        self.rejection_rate = 0.0
        self.no_response_rate = 0.0
        self.avg_score_all = 0.0
        self.avg_score_interviews = 0.0
        self.avg_score_rejections = 0.0
        self.patterns = []
        self.best_performing = []
        self.worst_performing = []
        self.score_distribution = {}
        self.company_type_analysis = {}
        self.role_type_analysis = {}
        self.skill_gap_patterns = []
        self.recommendations = []


class ApplicationPattern:
    def __init__(
        self,
        pattern_type: str,
        description: str,
        severity: str,
        evidence: list[str],
        recommendation: str,
    ):
        self.pattern_type = pattern_type
        self.description = description
        self.severity = severity  # high/medium/low
        self.evidence = evidence
        self.recommendation = recommendation


def analyze_postmortem(
    applications: list[ApplicationRecord],
    scores: dict[str, ScoreResult],
    jobs: dict[str, Job],
) -> PostmortemReport:
    report = PostmortemReport()
    report.total_applications = len(applications)

    if not applications:
        return report

    interviews = [
        a for a in applications
        if a.outcome in (OutcomeType.INTERVIEW, OutcomeType.OFFER)
    ]
    rejections = [
        a for a in applications
        if a.outcome == OutcomeType.REJECTION
    ]
    no_response = [
        a for a in applications
        if a.outcome == OutcomeType.NO_RESPONSE or a.outcome is None
    ]
    with_outcomes = [a for a in applications if a.outcome is not None]

    report.total_with_outcomes = len(with_outcomes)

    if report.total_applications > 0:
        report.interview_rate = round(
            len(interviews) / report.total_applications * 100, 1
        )
        report.rejection_rate = round(
            len(rejections) / report.total_applications * 100, 1
        )
        report.no_response_rate = round(
            len(no_response) / report.total_applications * 100, 1
        )

    all_scores = [
        scores[a.job_id].total_score
        for a in applications
        if a.job_id in scores
    ]
    interview_scores = [
        scores[a.job_id].total_score
        for a in interviews
        if a.job_id in scores
    ]
    rejection_scores = [
        scores[a.job_id].total_score
        for a in rejections
        if a.job_id in scores
    ]

    report.avg_score_all = round(
        sum(all_scores) / len(all_scores), 1
    ) if all_scores else 0.0
    report.avg_score_interviews = round(
        sum(interview_scores) / len(interview_scores), 1
    ) if interview_scores else 0.0
    report.avg_score_rejections = round(
        sum(rejection_scores) / len(rejection_scores), 1
    ) if rejection_scores else 0.0

    bands = {
        "90-100": 0, "80-89": 0, "70-79": 0,
        "60-69": 0, "50-59": 0, "below-50": 0,
    }
    for s in all_scores:
        if s >= 90:
            bands["90-100"] += 1
        elif s >= 80:
            bands["80-89"] += 1
        elif s >= 70:
            bands["70-79"] += 1
        elif s >= 60:
            bands["60-69"] += 1
        elif s >= 50:
            bands["50-59"] += 1
        else:
            bands["below-50"] += 1
    report.score_distribution = bands

    scored_apps = [
        (a, scores[a.job_id])
        for a in applications
        if a.job_id in scores
    ]
    scored_apps.sort(key=lambda x: x[1].total_score, reverse=True)
    report.best_performing = [
        {
            "job_id": a.job_id,
            "score": s.total_score,
            "outcome": a.outcome.value if a.outcome else "unknown",
            "company": jobs[a.job_id].company if a.job_id in jobs else "",
        }
        for a, s in scored_apps[:5]
    ]
    report.worst_performing = [
        {
            "job_id": a.job_id,
            "score": s.total_score,
            "outcome": a.outcome.value if a.outcome else "unknown",
            "company": jobs[a.job_id].company if a.job_id in jobs else "",
        }
        for a, s in scored_apps[-5:]
        if scored_apps
    ]

    report.patterns = _detect_patterns(
        applications, scores, jobs,
        interviews, rejections, no_response,
    )
    report.role_type_analysis = _analyze_role_types(
        applications, scores, jobs, interviews
    )
    report.skill_gap_patterns = _analyze_skill_gaps(
        applications, scores, rejections
    )
    report.recommendations = _generate_recommendations(report)

    return report


def _detect_patterns(
    applications, scores, jobs,
    interviews, rejections, no_response,
) -> list[ApplicationPattern]:
    patterns = []

    # Pattern 1: Applying below threshold
    low_score_apps = [
        a for a in applications
        if a.job_id in scores and scores[a.job_id].total_score < 60
    ]
    if len(low_score_apps) > len(applications) * 0.3:
        low_vals = [scores[a.job_id].total_score for a in low_score_apps if a.job_id in scores]
        patterns.append(ApplicationPattern(
            pattern_type="low_score_applications",
            description=(
                f"{len(low_score_apps)} applications "
                f"({len(low_score_apps)/len(applications):.0%}) "
                f"sent with score below 60"
            ),
            severity="high",
            evidence=[
                f"Score range: {min(low_vals)}–{max(low_vals)}"
            ],
            recommendation=(
                "Raise your threshold to 65+. "
                "Low-score applications waste time and "
                "signal desperation to recruiters."
            ),
        ))

    # Pattern 2: Score not predicting outcomes
    if interviews and rejections:
        int_scores = [
            scores[a.job_id].total_score
            for a in interviews if a.job_id in scores
        ]
        rej_scores = [
            scores[a.job_id].total_score
            for a in rejections if a.job_id in scores
        ]
        if int_scores and rej_scores:
            diff = abs(
                sum(int_scores) / len(int_scores) -
                sum(rej_scores) / len(rej_scores)
            )
            if diff < 5:
                patterns.append(ApplicationPattern(
                    pattern_type="score_not_predictive",
                    description=(
                        "Score difference between interviews "
                        "and rejections is less than 5 points"
                    ),
                    severity="medium",
                    evidence=[
                        "Score may not be well-calibrated yet",
                        "Need more outcome data to validate",
                    ],
                    recommendation=(
                        "Run nj calibrate --from-outcomes "
                        "after 20+ applications to recalibrate."
                    ),
                ))

    # Pattern 3: High no-response rate
    if len(no_response) > len(applications) * 0.7 and len(applications) >= 10:
        patterns.append(ApplicationPattern(
            pattern_type="high_no_response",
            description=(
                f"{len(no_response)/len(applications):.0%} "
                f"of applications received no response"
            ),
            severity="high",
            evidence=[
                "ATS may be filtering before human review",
                "CV may not be passing keyword scanning",
            ],
            recommendation=(
                "Run nj diagnose to identify ATS issues. "
                "Consider adding more role-specific keywords."
            ),
        ))

    # Pattern 4: Visa filtering missed
    visa_blocked = [
        a for a in applications
        if a.job_id in jobs and jobs[a.job_id].visa_label.value == "blocked"
    ]
    if visa_blocked:
        patterns.append(ApplicationPattern(
            pattern_type="visa_blocked_applications",
            description=(
                f"{len(visa_blocked)} applications sent "
                f"to visa-blocked companies"
            ),
            severity="high",
            evidence=[
                "Companies: " + ", ".join(
                    jobs[a.job_id].company
                    for a in visa_blocked[:3]
                    if a.job_id in jobs
                )
            ],
            recommendation=(
                "Enable skip_no_sponsorship in config. "
                "These applications will never convert."
            ),
        ))

    # Pattern 5: Weak experience sub-score
    exp_scores = [
        sub.score
        for a in applications
        if a.job_id in scores
        for sub in scores[a.job_id].sub_scores
        if sub.category.value == "experience_relevance"
    ]
    if exp_scores:
        avg_exp = sum(exp_scores) / len(exp_scores)
        if avg_exp < 55:
            patterns.append(ApplicationPattern(
                pattern_type="weak_experience_relevance",
                description=(
                    f"Average experience_relevance score: "
                    f"{avg_exp:.0f}/100 — consistently low"
                ),
                severity="high",
                evidence=[
                    "Work history not reading as ML engineering",
                    "IT/support roles dominating narrative",
                ],
                recommendation=(
                    "Reframe experience bullets to lead with "
                    "ML outcomes. Run nj diagnose for specifics."
                ),
            ))

    return patterns


def _analyze_role_types(
    applications, scores, jobs, interviews
) -> dict:
    role_outcomes: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "interviews": 0, "avg_score": []}
    )
    interview_ids = {a.job_id for a in interviews}

    for app in applications:
        job = jobs.get(app.job_id)
        if not job:
            continue
        role_type = _categorize_role(job.title)
        role_outcomes[role_type]["total"] += 1
        if app.job_id in interview_ids:
            role_outcomes[role_type]["interviews"] += 1
        if app.job_id in scores:
            role_outcomes[role_type]["avg_score"].append(
                scores[app.job_id].total_score
            )

    result = {}
    for role, data in role_outcomes.items():
        avg = (
            sum(data["avg_score"]) / len(data["avg_score"])
            if data["avg_score"] else 0
        )
        result[role] = {
            "total": data["total"],
            "interviews": data["interviews"],
            "interview_rate": round(
                data["interviews"] / data["total"] * 100, 1
            ) if data["total"] > 0 else 0,
            "avg_score": round(avg, 1),
        }
    return result


def _analyze_skill_gaps(
    applications, scores, rejections
) -> list[dict]:
    missing_in_rejections: Counter = Counter()
    for app in rejections:
        if app.job_id in scores:
            for skill in scores[app.job_id].missing_skills:
                missing_in_rejections[skill] += 1

    if not missing_in_rejections:
        return []

    total_rejections = max(len(rejections), 1)
    return [
        {
            "skill": skill,
            "rejection_frequency": count,
            "pct_of_rejections": round(count / total_rejections * 100, 1),
        }
        for skill, count in missing_in_rejections.most_common(8)
        if count >= 2
    ]


def _generate_recommendations(report: PostmortemReport) -> list[str]:
    recs = []

    if report.interview_rate == 0 and report.total_applications >= 5:
        recs.append(
            f"Zero interviews from {report.total_applications} applications — "
            "run nj diagnose immediately"
        )

    if report.avg_score_all < 65:
        recs.append(
            f"Average score {report.avg_score_all} is low — "
            "raise threshold and be more selective"
        )

    if (report.avg_score_interviews > report.avg_score_rejections + 8
            and report.avg_score_interviews > 0):
        recs.append(
            f"Scores predict outcomes "
            f"(interviews avg {report.avg_score_interviews} vs rejections "
            f"{report.avg_score_rejections}) — "
            f"raise threshold to {int(report.avg_score_interviews - 5)}"
        )

    high_patterns = [p for p in report.patterns if p.severity == "high"]
    for p in high_patterns[:2]:
        recs.append(p.recommendation)

    if not recs:
        recs.append(
            "Not enough outcome data yet. "
            "Keep applying and run nj watch to track callbacks."
        )

    return recs


def _categorize_role(title: str) -> str:
    title_lower = title.lower()
    if any(w in title_lower for w in ["machine learning", "ml engineer", "mlops"]):
        return "ML Engineer"
    if any(w in title_lower for w in ["computer vision", "cv engineer", "vision"]):
        return "CV Engineer"
    if any(w in title_lower for w in ["data scientist", "data science"]):
        return "Data Science"
    if any(w in title_lower for w in ["research", "scientist"]):
        return "Research"
    if any(w in title_lower for w in ["nlp", "natural language"]):
        return "NLP"
    if any(w in title_lower for w in ["ai engineer", "artificial intelligence"]):
        return "AI Engineer"
    return "Other"
