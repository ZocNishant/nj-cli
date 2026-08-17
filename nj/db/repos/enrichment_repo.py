from __future__ import annotations

from datetime import UTC, datetime

from nj.db.engine import get_session
from nj.db.models import JobEnrichmentORM
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class EnrichmentRepo:
    def __init__(self, db_path: str = "data/nj.db") -> None:
        self.db_path = db_path

    def save_enrichment(self, job_id: str, enrichment: dict) -> None:
        sponsor = enrichment.get("sponsorship") or {}
        salary = enrichment.get("salary") or {}
        semantic = enrichment.get("semantic") or {}
        uscis = enrichment.get("uscis_profile") or {}

        with get_session(self.db_path) as session:
            existing = session.get(JobEnrichmentORM, job_id)
            data = {
                "job_id": job_id,
                "sponsorship_prob": sponsor.get("probability"),
                "sponsorship_tier": sponsor.get("tier"),
                "predicted_salary": salary.get("predicted_salary"),
                "salary_low": (salary.get("range") or {}).get("low"),
                "salary_high": (salary.get("range") or {}).get("high"),
                "semantic_score": semantic.get("score"),
                "uscis_petitions": uscis.get("total_petitions"),
                "uscis_approval_rate": uscis.get("approval_rate"),
                "uscis_sponsor_tier": uscis.get("sponsor_tier"),
                "enriched_at": datetime.now(UTC),
            }
            if existing:
                for k, v in data.items():
                    if k != "job_id":
                        setattr(existing, k, v)
            else:
                session.add(JobEnrichmentORM(**data))

    def get_enrichment(self, job_id: str) -> dict | None:
        with get_session(self.db_path) as session:
            row = session.get(JobEnrichmentORM, job_id)
            if not row:
                return None
            return {
                "sponsorship": {
                    "probability": row.sponsorship_prob,
                    "tier": row.sponsorship_tier,
                }
                if row.sponsorship_prob is not None
                else None,
                "salary": {
                    "predicted_salary": row.predicted_salary,
                    "range": {
                        "low": row.salary_low,
                        "high": row.salary_high,
                    },
                }
                if row.predicted_salary is not None
                else None,
                "semantic": {"score": row.semantic_score}
                if row.semantic_score is not None
                else None,
                "uscis_profile": {
                    "total_petitions": row.uscis_petitions,
                    "approval_rate": row.uscis_approval_rate,
                    "sponsor_tier": row.uscis_sponsor_tier,
                }
                if row.uscis_petitions is not None
                else None,
            }

    def get_enrichments_for_jobs(self, job_ids: list[str]) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for job_id in job_ids:
            enrichment = self.get_enrichment(job_id)
            if enrichment:
                result[job_id] = enrichment
        return result
