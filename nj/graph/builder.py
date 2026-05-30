from __future__ import annotations

from nj.graph.repo import GraphRepo
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class GraphBuilder:
    def __init__(self, db_path: str = "data/nj.db") -> None:
        self.repo = GraphRepo(db_path)
        self.db_path = db_path

    def build_from_cv(self, cv_base: dict) -> dict:
        counts: dict[str, int] = {"nodes": 0, "edges": 0}
        personal = cv_base.get("personal", {})
        name = personal.get("name", "Candidate")

        person_id = self.repo.get_or_create_node(
            "person",
            name,
            properties={
                "visa": personal.get("work_authorization", ""),
                "graduation": personal.get("graduation_date", ""),
            },
            source="cv_base",
        )
        counts["nodes"] += 1

        skills = cv_base.get("skills", {})
        for category, items in skills.items():
            if not isinstance(items, list):
                continue
            for skill in items:
                skill_id = self.repo.get_or_create_node(
                    "skill",
                    skill,
                    properties={"category": category},
                    source="cv_base",
                )
                self.repo.get_or_create_edge(
                    person_id,
                    skill_id,
                    "HAS_SKILL",
                    weight=1.0,
                    source="cv_base",
                )
                counts["nodes"] += 1
                counts["edges"] += 1

        for exp in cv_base.get("experience", []):
            if not isinstance(exp, dict):
                continue
            company = exp.get("company", "")
            title = exp.get("title", "")
            if not company:
                continue
            company_id = self.repo.get_or_create_node(
                "company",
                company,
                properties={"status": exp.get("status")},
                source="cv_base",
            )
            self.repo.get_or_create_edge(
                person_id,
                company_id,
                "WORKED_AT",
                properties={
                    "title": title,
                    "start": exp.get("start"),
                    "end": exp.get("end"),
                },
                source="cv_base",
            )
            counts["nodes"] += 1
            counts["edges"] += 1

        for proj in cv_base.get("projects", []):
            if not isinstance(proj, dict):
                continue
            name_proj = proj.get("name", "")
            if not name_proj:
                continue
            proj_id = self.repo.get_or_create_node(
                "project",
                name_proj,
                properties={
                    "anchor": proj.get("anchor", False),
                    "date": proj.get("date", ""),
                },
                source="cv_base",
            )
            self.repo.get_or_create_edge(
                person_id,
                proj_id,
                "BUILT",
                weight=1.0,
                source="cv_base",
            )
            counts["nodes"] += 1
            counts["edges"] += 1
            for tech in proj.get("tech", []):
                tech_id = self.repo.get_or_create_node(
                    "technology",
                    tech,
                    source="cv_base",
                )
                self.repo.get_or_create_edge(
                    proj_id,
                    tech_id,
                    "USES_TECH",
                    weight=1.0,
                    source="cv_base",
                )

        for edu in cv_base.get("education", []):
            if not isinstance(edu, dict):
                continue
            inst = edu.get("institution", "")
            if not inst:
                continue
            inst_id = self.repo.get_or_create_node(
                "institution",
                inst,
                properties={
                    "degree": edu.get("degree"),
                    "end": edu.get("end"),
                },
                source="cv_base",
            )
            self.repo.get_or_create_edge(
                person_id,
                inst_id,
                "STUDIED_AT",
                weight=1.0,
                source="cv_base",
            )
            counts["nodes"] += 1
            counts["edges"] += 1

        logger.info(
            "graph_built_from_cv",
            nodes=counts["nodes"],
            edges=counts["edges"],
        )
        return counts

    def add_job_application(
        self,
        job_title: str,
        company: str,
        score: int,
        matched_skills: list[str],
        missing_skills: list[str],
        outcome: str | None = None,
    ) -> None:
        repo = self.repo
        person_nodes = repo.get_nodes_by_type("person")
        if not person_nodes:
            return
        person_id = person_nodes[0].id

        role_id = repo.get_or_create_node(
            "role",
            job_title,
            properties={"last_score": score},
            source="application",
        )
        repo.get_or_create_edge(
            person_id,
            role_id,
            "APPLIED_TO",
            weight=score / 100,
            properties={
                "score": score,
                "company": company,
                "outcome": outcome,
            },
            source="application",
        )

        company_id = repo.get_or_create_node(
            "company",
            company,
            source="application",
        )
        repo.get_or_create_edge(
            person_id,
            company_id,
            "APPLIED_TO",
            properties={"role": job_title},
            source="application",
        )

        for skill in matched_skills:
            skill_id = repo.get_or_create_node(
                "skill",
                skill,
                source="application",
            )
            repo.get_or_create_edge(
                person_id,
                skill_id,
                "HAS_SKILL",
                weight=1.2,
                source="application",
            )

        for skill in missing_skills:
            skill_id = repo.get_or_create_node(
                "skill",
                skill,
                properties={"is_gap": True},
                source="application",
            )
            repo.get_or_create_edge(
                role_id,
                skill_id,
                "REQUIRES",
                weight=1.0,
                source="application",
            )

        if outcome:
            outcome_id = repo.get_or_create_node(
                "outcome",
                outcome,
                source="application",
            )
            repo.get_or_create_edge(
                role_id,
                outcome_id,
                "OUTCOME",
                weight=1.0,
                source="application",
            )

    def build_from_scores(self, db_path: str | None = None) -> dict:
        dp = db_path or self.db_path
        counts: dict[str, int] = {"nodes": 0, "edges": 0}
        try:
            from nj.db.repos.job_repo import JobRepo
            from nj.db.repos.score_repo import ScoreRepo

            job_repo = JobRepo(dp)
            score_repo = ScoreRepo(dp)
            jobs = job_repo.get_jobs()
            for job in jobs:
                score = score_repo.get_score(job.id)
                if not score:
                    continue
                self.add_job_application(
                    job_title=job.title,
                    company=job.company,
                    score=score.total_score,
                    matched_skills=score.matched_skills,
                    missing_skills=score.missing_skills,
                )
                counts["nodes"] += 1
                counts["edges"] += 1
        except Exception as e:
            logger.warning("graph_build_from_scores_failed", error=str(e))
        return counts
