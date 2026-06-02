"""
Salary estimator for ML/AI roles.
Rule-based approach using 2023-2024 ML job market benchmarks.
No training data required — USCIS aggregated data has no wage info.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

from nj.utils.logger import get_logger

logger = get_logger(__name__)

MODEL_PATH = Path("data/models/salary_model.pkl")

ROLE_CATEGORIES: dict[str, list[str]] = {
    "ml_engineer": ["machine learning", "ml engineer", "mlops"],
    "data_scientist": ["data scientist", "data science"],
    "research_scientist": [
        "research scientist",
        "applied scientist",
        "ai researcher",
    ],
    "cv_engineer": [
        "computer vision",
        "vision engineer",
        "image",
        "cv engineer",
    ],
    "nlp_engineer": ["nlp", "natural language", "llm engineer"],
    "data_engineer": ["data engineer", "pipeline", "etl"],
    "software_engineer": ["software engineer", "swe", "backend", "fullstack"],
}

STATE_TIERS: dict[str, float] = {
    "CA": 1.3,
    "NY": 1.25,
    "WA": 1.2,
    "MA": 1.15,
    "TX": 1.0,
    "IL": 1.0,
    "GA": 0.95,
    "FL": 0.95,
    "CO": 1.05,
    "VA": 1.05,
    "NC": 0.95,
    "AZ": 0.95,
    "OR": 1.1,
    "NJ": 1.15,
    "PA": 1.0,
}


class SalaryModel:
    def __init__(self) -> None:
        self.model = None
        self.is_trained = False
        self.training_samples = 0
        self.feature_means: dict = {}

    def train(self, db_path: str = "data/nj.db") -> dict:
        """
        Salary model uses market benchmarks — no training needed.
        Returns success immediately.
        """
        self.is_trained = True
        self._save_trained_flag()
        return {
            "success": True,
            "training_samples": 0,
            "r2_score": None,
            "note": "Uses 2024 ML market benchmarks. No DB training required.",
            "salary_range": {
                "min": 100000,
                "median": 150000,
                "max": 220000,
            },
        }

    def predict(
        self,
        job_title: str,
        state: str = "CA",
        year: int = 2024,
        is_ml: bool = True,
    ) -> dict:
        """
        Rule-based salary estimator using ML job market data.
        Based on 2023-2024 ML role salary benchmarks.
        No training needed — uses curated salary bands.
        """
        role_cat = self._get_role_category(job_title)
        state_tier = STATE_TIERS.get(state.upper(), 1.0)

        BASE_SALARIES = {
            "ml_engineer":        155000,
            "research_scientist": 170000,
            "data_scientist":     135000,
            "cv_engineer":        150000,
            "nlp_engineer":       160000,
            "data_engineer":      130000,
            "software_engineer":  145000,
        }

        base = BASE_SALARIES.get(role_cat, 140000)

        predicted = int(base * state_tier)

        year_adj = 1.0 + (year - 2024) * 0.03
        predicted = int(predicted * year_adj)

        low = int(predicted * 0.85)
        high = int(predicted * 1.20)

        state_note = ""
        if state_tier >= 1.2:
            state_note = f"{state} is a high-cost market (+{int((state_tier - 1) * 100)}%)"
        elif state_tier <= 0.95:
            state_note = f"{state} is below national median ({int((state_tier - 1) * 100)}%)"

        return {
            "predicted_salary": predicted,
            "range": {"low": low, "high": high},
            "confidence": "medium",
            "state_note": state_note,
            "role_category": role_cat,
            "source": "market_benchmark",
        }

    def _extract_features(
        self,
        job_title: str,
        state: str,
        year: int,
        is_ml: bool,
    ) -> list[float]:
        role_cat = self._get_role_category(job_title)
        role_cats = list(ROLE_CATEGORIES.keys())
        role_idx = float(
            role_cats.index(role_cat) if role_cat in role_cats else 0
        )
        state_tier = float(STATE_TIERS.get(state.upper(), 1.0))
        year_norm = (year - 2020) / 5
        return [role_idx, state_tier, year_norm, 1.0 if is_ml else 0.0]

    def _get_role_category(self, title: str) -> str:
        title_lower = title.lower()
        for cat, keywords in ROLE_CATEGORIES.items():
            if any(kw in title_lower for kw in keywords):
                return cat
        return "software_engineer"

    def _save_trained_flag(self) -> None:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({"trained": True, "source": "benchmark"}, f)

    def _load(self) -> bool:
        if not MODEL_PATH.exists():
            return False
        try:
            with open(MODEL_PATH, "rb") as f:
                pickle.load(f)
            self.is_trained = True
            return True
        except Exception:
            return False


_salary_model: SalaryModel | None = None


def get_salary_model() -> SalaryModel:
    global _salary_model
    if _salary_model is None:
        _salary_model = SalaryModel()
        _salary_model._load()
    return _salary_model
