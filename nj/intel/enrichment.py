"""
Job enrichment pipeline.
Runs after scraping, before scoring.
Enriches each job with:
- H1B sponsorship probability (ML model)
- Predicted salary range (ML model)
- USCIS company profile
- Semantic CV-JD similarity
- Career graph context
"""

from __future__ import annotations

import re

from nj.models.job import Job
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class JobEnrichment:
    def __init__(self, db_path: str = "data/nj.db") -> None:
        self.db_path = db_path
        self._sponsor_model = None
        self._salary_model = None
        self._semantic_model = None

    def enrich(
        self,
        job: Job,
        cv_base: dict | None = None,
    ) -> dict:
        enrichment: dict = {
            "job_id": job.id,
            "sponsorship": None,
            "salary": None,
            "semantic": None,
            "uscis_profile": None,
            "graph_context": None,
        }

        try:
            enrichment["sponsorship"] = self._get_sponsorship(job)
        except Exception as e:
            logger.debug("enrichment_sponsorship_failed", error=str(e))

        try:
            enrichment["salary"] = self._get_salary(job)
        except Exception as e:
            logger.debug("enrichment_salary_failed", error=str(e))

        try:
            enrichment["uscis_profile"] = self._get_uscis_profile(job)
        except Exception as e:
            logger.debug("enrichment_uscis_failed", error=str(e))

        if cv_base:
            try:
                enrichment["semantic"] = self._get_semantic(job, cv_base)
            except Exception as e:
                logger.debug("enrichment_semantic_failed", error=str(e))

        try:
            enrichment["graph_context"] = self._get_graph_context(job)
        except Exception as e:
            logger.debug("enrichment_graph_failed", error=str(e))

        return enrichment

    def enrich_batch(
        self,
        jobs: list[Job],
        cv_base: dict | None = None,
    ) -> dict[str, dict]:
        enrichments: dict[str, dict] = {}
        for job in jobs:
            enrichments[job.id] = self.enrich(job, cv_base)
        return enrichments

    def _get_sponsorship(self, job: Job) -> dict | None:
        if self._sponsor_model is None:
            from nj.ml.sponsorship_model import get_sponsorship_model

            self._sponsor_model = get_sponsorship_model()
        if not self._sponsor_model.is_trained:
            return None
        state = self._extract_state(job.location)
        return self._sponsor_model.predict(
            company_name=job.company,
            job_title=job.title,
            state=state,
        )

    def _get_salary(self, job: Job) -> dict | None:
        if self._salary_model is None:
            from nj.ml.salary_model import get_salary_model

            self._salary_model = get_salary_model()
        if not self._salary_model.is_trained:
            return None
        state = self._extract_state(job.location)
        return self._salary_model.predict(
            job_title=job.title,
            state=state,
        )

    def _get_uscis_profile(self, job: Job) -> dict | None:
        from nj.db.repos.intel_repo import IntelRepo

        repo = IntelRepo(self.db_path)
        stats = repo.get_stats()
        if stats["total_petitions"] == 0:
            return None
        profile = repo.get_company_profile(job.company)
        if not profile:
            return None
        # Convert approval_rate (0.0–1.0) to percentage for display
        raw_rate = profile.get("approval_rate", 0)
        return {
            "total_petitions": profile.get("total_petitions", 0),
            "approval_rate": round(raw_rate * 100, 1),
            "ml_ai_petitions": profile.get("ml_ai_petitions", 0),
            "sponsor_tier": profile.get("sponsor_tier", "UNKNOWN"),
            "median_salary": profile.get("median_salary"),
        }

    def _get_semantic(self, job: Job, cv_base: dict) -> dict | None:
        if self._semantic_model is None:
            from nj.ml.semantic_model import get_semantic_model

            self._semantic_model = get_semantic_model()
        if not self._semantic_model.is_loaded:
            loaded = self._semantic_model.load()
            if not loaded:
                return None
        result = self._semantic_model.score_cv_jd(cv_base, job.description)
        if result.get("semantic_score") is None:
            return None
        return {
            "score": result["semantic_score"],
            "top_section": result.get("top_section"),
            "weak_section": result.get("weak_section"),
            "interpretation": result.get("interpretation"),
        }

    def _get_graph_context(self, job: Job) -> dict | None:
        from nj.graph.repo import GraphRepo

        repo = GraphRepo(self.db_path)
        stats = repo.get_graph_stats()
        if stats["total_nodes"] == 0:
            return None
        companies = repo.get_nodes_by_type("company")
        company_match = next(
            (c for c in companies if repo.normalize(job.company) in c.label_normalized),
            None,
        )
        if company_match:
            return {
                "company_in_graph": True,
                "company_label": company_match.label,
                "node_id": company_match.id,
            }
        return {"company_in_graph": False}

    def _extract_state(self, location: str) -> str:
        if not location:
            return "CA"
        match = re.search(r",\s*([A-Z]{2})\b", location)
        if match:
            return match.group(1)
        state_names = {
            "california": "CA",
            "new york": "NY",
            "texas": "TX",
            "washington": "WA",
            "massachusetts": "MA",
            "florida": "FL",
            "illinois": "IL",
            "georgia": "GA",
            "colorado": "CO",
            "virginia": "VA",
            "remote": "CA",
        }
        loc_lower = location.lower()
        for name, code in state_names.items():
            if name in loc_lower:
                return code
        return "CA"
