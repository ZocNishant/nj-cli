"""
Salary predictor for ML/AI roles.
Trained on USCIS H1B wage disclosure data.
Predicts salary range given role + location.

Stack: scikit-learn GradientBoosting regression
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
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import cross_val_score

        logger.info("salary_model_training_start")
        X, y = self._load_training_data(db_path)

        if len(X) < 50:
            return {
                "success": False,
                "error": "Not enough salary data. Run nj intel sync first.",
            }

        X_arr = np.array(X)
        y_arr = np.array(y)

        self.model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )
        self.model.fit(X_arr, y_arr)
        self.is_trained = True
        self.training_samples = len(X)

        try:
            scores = cross_val_score(
                self.model, X_arr, y_arr, cv=3, scoring="r2"
            )
            r2 = round(float(np.mean(scores)), 3)
        except Exception:
            r2 = None

        self._save()
        metrics: dict = {
            "success": True,
            "training_samples": len(X),
            "r2_score": r2,
            "salary_range": {
                "min": int(np.percentile(y_arr, 10)),
                "median": int(np.median(y_arr)),
                "max": int(np.percentile(y_arr, 90)),
            },
        }
        logger.info("salary_model_trained", **metrics)
        return metrics

    def predict(
        self,
        job_title: str,
        state: str = "CA",
        year: int = 2024,
        is_ml: bool = True,
    ) -> dict:
        if not self.is_trained:
            if not self._load():
                return {
                    "predicted_salary": None,
                    "range": None,
                    "confidence": "low",
                    "reason": "Model not trained.",
                }

        features = self._extract_features(job_title, state, year, is_ml)
        X = np.array([features])
        pred = float(self.model.predict(X)[0])
        pred = max(40_000, min(pred, 500_000))
        low = pred * 0.85
        high = pred * 1.15

        state_note = ""
        tier = STATE_TIERS.get(state.upper(), 1.0)
        if tier >= 1.2:
            state_note = f"{state} is a high-cost market"
        elif tier <= 0.95:
            state_note = f"{state} is below national median"

        return {
            "predicted_salary": int(pred),
            "range": {"low": int(low), "high": int(high)},
            "confidence": "medium",
            "state_note": state_note,
            "role_category": self._get_role_category(job_title),
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

    def _load_training_data(self, db_path: str) -> tuple[list, list]:
        from nj.db.engine import get_engine
        from sqlalchemy import text as sa_text

        X: list[list[float]] = []
        y: list[float] = []
        engine = get_engine(db_path)
        with engine.connect() as conn:
            rows = conn.execute(
                sa_text(
                    "SELECT job_title, worksite_state, "
                    "year, is_ml_role, wage_from "
                    "FROM h1b_petitions "
                    "WHERE wage_from > 40000 "
                    "AND wage_from < 500000 "
                    "AND case_status LIKE '%Certif%' "
                    "LIMIT 30000"
                )
            ).fetchall()

        for row in rows:
            title, state, yr, is_ml, wage = row
            if not wage:
                continue
            features = self._extract_features(
                title or "",
                state or "CA",
                yr or 2024,
                bool(is_ml),
            )
            X.append(features)
            y.append(float(wage))

        return X, y

    def _save(self) -> None:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(
                {
                    "model": self.model,
                    "training_samples": self.training_samples,
                },
                f,
            )

    def _load(self) -> bool:
        if not MODEL_PATH.exists():
            return False
        try:
            with open(MODEL_PATH, "rb") as f:
                data = pickle.load(f)
            self.model = data["model"]
            self.training_samples = data.get("training_samples", 0)
            self.is_trained = True
            return True
        except Exception as e:
            logger.warning("salary_model_load_failed", error=str(e))
            return False


_salary_model: SalaryModel | None = None


def get_salary_model() -> SalaryModel:
    global _salary_model
    if _salary_model is None:
        _salary_model = SalaryModel()
        _salary_model._load()
    return _salary_model
