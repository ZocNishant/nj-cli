from __future__ import annotations

from nj.db.engine import get_session
from nj.db.models import ScoreResultORM
from nj.models.score import ScoreResult, SubScore


def _to_model(row: ScoreResultORM) -> ScoreResult:
    return ScoreResult(
        job_id=row.job_id,
        total_score=row.total_score,
        confidence=row.confidence,
        sub_scores=[SubScore(**s) for s in (row.sub_scores or [])],
        matched_skills=row.matched_skills or [],
        missing_skills=row.missing_skills or [],
        recommended_emphasis=row.recommended_emphasis or [],
        visa_compatible=row.visa_compatible,
        visa_notes=row.visa_notes or "",
        overall_rationale=row.overall_rationale or "",
        scored_at=row.scored_at,
        provider=row.provider or "",
        prompt_version=row.prompt_version or "",
        raw_response=row.raw_response,
    )


class ScoreRepo:
    def __init__(self, db_path: str = "data/nj.db"):
        self.db_path = db_path

    def save_score(self, result: ScoreResult) -> None:
        raw = result.raw_response[:2000] if result.raw_response else None
        with get_session(self.db_path) as session:
            sub = [s.model_dump() for s in result.sub_scores]
            existing = session.get(ScoreResultORM, result.job_id)
            if existing:
                existing.total_score = result.total_score
                existing.confidence = result.confidence
                existing.sub_scores = sub
                existing.matched_skills = result.matched_skills
                existing.missing_skills = result.missing_skills
                existing.recommended_emphasis = result.recommended_emphasis
                existing.visa_compatible = result.visa_compatible
                existing.visa_notes = result.visa_notes
                existing.overall_rationale = result.overall_rationale
                existing.scored_at = result.scored_at
                existing.provider = result.provider
                existing.prompt_version = result.prompt_version
                existing.raw_response = raw
            else:
                session.add(
                    ScoreResultORM(
                        job_id=result.job_id,
                        total_score=result.total_score,
                        confidence=result.confidence,
                        sub_scores=sub,
                        matched_skills=result.matched_skills,
                        missing_skills=result.missing_skills,
                        recommended_emphasis=result.recommended_emphasis,
                        visa_compatible=result.visa_compatible,
                        visa_notes=result.visa_notes,
                        overall_rationale=result.overall_rationale,
                        scored_at=result.scored_at,
                        provider=result.provider,
                        prompt_version=result.prompt_version,
                        raw_response=raw,
                    )
                )

    def get_all_scores(self) -> list[ScoreResult]:
        with get_session(self.db_path) as session:
            rows = session.query(ScoreResultORM).all()
            return [_to_model(r) for r in rows]

    def get_score(self, job_id: str) -> ScoreResult | None:
        with get_session(self.db_path) as session:
            row = session.get(ScoreResultORM, job_id)
            if not row:
                return None
            return _to_model(row)

    def get_scores_with_failures(self) -> list[ScoreResult]:
        with get_session(self.db_path) as session:
            rows = (
                session.query(ScoreResultORM)
                .filter(ScoreResultORM.total_score == 0)
                .all()
            )
            return [_to_model(r) for r in rows]

    def get_parse_failure_rate(self) -> dict:
        with get_session(self.db_path) as session:
            total = session.query(ScoreResultORM).count()
            failures = (
                session.query(ScoreResultORM)
                .filter(ScoreResultORM.total_score == 0)
                .count()
            )
            return {
                "total": total,
                "failures": failures,
                "rate_pct": round(failures / total * 100, 1) if total > 0 else 0.0,
            }
