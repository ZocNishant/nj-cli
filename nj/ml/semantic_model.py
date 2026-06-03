"""
Semantic CV-JD similarity using sentence transformers.
Replaces/augments keyword-based scoring with semantic matching.

Model: all-MiniLM-L6-v2 (80MB, runs locally, fast)
No training needed — pre-trained embeddings.
"""

from __future__ import annotations

import numpy as np

from nj.utils.logger import get_logger

logger = get_logger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
_semantic_warned = False


class SemanticModel:
    def __init__(self) -> None:
        self.model = None
        self.is_loaded = False

    def load(self) -> bool:
        global _semantic_warned
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("loading_semantic_model", model=MODEL_NAME)
            self.model = SentenceTransformer(MODEL_NAME)
            self.is_loaded = True
            logger.info("semantic_model_loaded")
            return True
        except ImportError:
            if not _semantic_warned:
                logger.warning(
                    "sentence_transformers_not_installed",
                    hint="pip install sentence-transformers",
                )
                _semantic_warned = True
            return False
        except Exception as e:
            logger.warning("semantic_model_load_failed", error=str(e))
            return False

    def score_cv_jd(
        self,
        cv_base: dict,
        job_description: str,
    ) -> dict:
        if not self.is_loaded:
            if not self.load():
                return {
                    "semantic_score": None,
                    "section_scores": {},
                    "reason": (
                        "sentence-transformers not installed. "
                        "Run: pip install sentence-transformers"
                    ),
                }

        sections = self._extract_cv_sections(cv_base)
        jd_clean = job_description[:3000]

        scores: dict[str, float] = {}
        embeddings_jd = self.model.encode([jd_clean], convert_to_numpy=True)

        for section_name, section_text in sections.items():
            if not section_text.strip():
                continue
            emb_section = self.model.encode([section_text], convert_to_numpy=True)
            similarity = float(
                self._cosine_similarity(emb_section[0], embeddings_jd[0])
            )
            scores[section_name] = round(similarity, 3)

        if not scores:
            return {"semantic_score": 0.0, "section_scores": {}}

        weights = {
            "projects": 0.35,
            "skills": 0.25,
            "experience": 0.25,
            "education": 0.10,
            "summary": 0.05,
        }
        weighted_sum = 0.0
        weight_total = 0.0
        for section, score in scores.items():
            w = weights.get(section, 0.05)
            weighted_sum += score * w
            weight_total += w

        overall = weighted_sum / weight_total if weight_total > 0 else 0.0
        overall_100 = round(overall * 100, 1)

        top_section = max(scores, key=scores.__getitem__) if scores else ""
        weak_section = min(scores, key=scores.__getitem__) if scores else ""

        return {
            "semantic_score": overall_100,
            "section_scores": {k: round(v * 100, 1) for k, v in scores.items()},
            "top_section": top_section,
            "weak_section": weak_section,
            "interpretation": self._interpret(overall),
        }

    def find_semantic_gaps(
        self,
        cv_base: dict,
        job_description: str,
        top_n: int = 5,
    ) -> list[dict]:
        if not self.is_loaded:
            if not self.load():
                return []

        jd_sentences = [
            s.strip() for s in job_description.split(".") if len(s.strip()) > 20
        ][:20]
        cv_text = self._cv_to_text(cv_base)
        if not jd_sentences or not cv_text:
            return []

        cv_emb = self.model.encode([cv_text], convert_to_numpy=True)[0]
        jd_embs = self.model.encode(jd_sentences, convert_to_numpy=True)

        gaps = []
        for i, jd_sent in enumerate(jd_sentences):
            sim = float(self._cosine_similarity(cv_emb, jd_embs[i]))
            if sim < 0.35:
                gaps.append(
                    {
                        "jd_requirement": jd_sent[:100],
                        "similarity": round(sim, 3),
                        "gap_severity": "high" if sim < 0.2 else "medium",
                    }
                )

        gaps.sort(key=lambda x: x["similarity"])
        return gaps[:top_n]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _extract_cv_sections(self, cv_base: dict) -> dict[str, str]:
        sections: dict[str, str] = {}

        skills = cv_base.get("skills", {})
        skill_text = " ".join(
            item
            for items in skills.values()
            if isinstance(items, list)
            for item in items
        )
        if skill_text:
            sections["skills"] = skill_text

        proj_texts = []
        for p in cv_base.get("projects", []):
            if isinstance(p, dict):
                name = p.get("name", "")
                tech = " ".join(p.get("tech", []))
                bullets = " ".join(p.get("bullets", []))
                proj_texts.append(f"{name} {tech} {bullets}")
        if proj_texts:
            sections["projects"] = " ".join(proj_texts)

        exp_texts = []
        for e in cv_base.get("experience", []):
            if isinstance(e, dict):
                title = e.get("title", "")
                company = e.get("company", "")
                bullets = " ".join(e.get("bullets", []))
                exp_texts.append(f"{title} {company} {bullets}")
        if exp_texts:
            sections["experience"] = " ".join(exp_texts)

        edu_texts = []
        for edu in cv_base.get("education", []):
            if isinstance(edu, dict):
                degree = edu.get("degree", "")
                courses = " ".join(edu.get("courses", []))
                edu_texts.append(f"{degree} {courses}")
        if edu_texts:
            sections["education"] = " ".join(edu_texts)

        summary = cv_base.get("summary", "")
        if summary:
            sections["summary"] = summary

        return sections

    def _cv_to_text(self, cv_base: dict) -> str:
        sections = self._extract_cv_sections(cv_base)
        return " ".join(sections.values())

    def _interpret(self, score: float) -> str:
        if score >= 0.7:
            return "Strong semantic match"
        elif score >= 0.5:
            return "Moderate semantic match"
        elif score >= 0.35:
            return "Weak semantic match — consider tailoring"
        else:
            return "Low semantic match — role may not fit profile"


_semantic_model: SemanticModel | None = None


def get_semantic_model() -> SemanticModel:
    global _semantic_model
    if _semantic_model is None:
        _semantic_model = SemanticModel()
    return _semantic_model
