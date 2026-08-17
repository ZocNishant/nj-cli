"""
Sponsorship probability classifier.
Trained on USCIS H1B petition data.
Predicts likelihood a company sponsors a given role.

Stack: scikit-learn RandomForest + TF-IDF
Training data: h1b_petitions table (loaded via nj intel sync)
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

from nj.utils.logger import get_logger

logger = get_logger(__name__)

MODEL_PATH = Path("data/models/sponsorship_model.pkl")
MIN_TRAINING_SAMPLES = 100


class SponsorshipModel:
    def __init__(self) -> None:
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        self.is_trained = False
        self.training_samples = 0
        self.feature_names: list[str] = []

    def train(self, db_path: str = "data/nj.db") -> dict:
        from scipy.sparse import csr_matrix, hstack
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.model_selection import cross_val_score
        from sklearn.preprocessing import LabelEncoder

        logger.info("sponsorship_model_training_start")

        X_text, X_meta, y = self._load_training_data(db_path)

        if len(X_text) < MIN_TRAINING_SAMPLES:
            return {
                "success": False,
                "error": (f"Not enough data: {len(X_text)} samples. Run nj intel sync first."),
            }

        self.vectorizer = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 2),
            min_df=2,
        )
        X_tfidf = self.vectorizer.fit_transform(X_text)

        self.label_encoder = LabelEncoder()
        states = [m[0] for m in X_meta]
        states_encoded = self.label_encoder.fit_transform(states).reshape(-1, 1)
        years = np.array([m[1] for m in X_meta]).reshape(-1, 1)
        counts = np.array([m[2] for m in X_meta]).reshape(-1, 1)

        X_combined = hstack(
            [
                X_tfidf,
                csr_matrix(states_encoded),
                csr_matrix(years),
                csr_matrix(counts),
            ]
        )

        y_arr = np.array(y)

        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_combined, y_arr)
        self.is_trained = True
        self.training_samples = len(X_text)

        try:
            cv_scores = cross_val_score(self.model, X_combined, y_arr, cv=3, scoring="roc_auc")
            auc = round(float(np.mean(cv_scores)), 3)
        except Exception:
            auc = None

        tfidf_features = self.vectorizer.get_feature_names_out()
        importances = self.model.feature_importances_
        top_features = [
            tfidf_features[i] for i in np.argsort(importances[: len(tfidf_features)])[-10:][::-1]
        ]

        self._save()

        metrics = {
            "success": True,
            "training_samples": len(X_text),
            "positive_rate": round(float(np.mean(y_arr)), 3),
            "auc_roc": auc,
            "top_features": list(top_features),
        }
        logger.info("sponsorship_model_trained", **metrics)
        return metrics

    def predict(
        self,
        company_name: str,
        job_title: str,
        state: str = "CA",
        year: int = 2024,
        petition_count: int = 1,
    ) -> dict:
        if not self.is_trained:
            if not self._load():
                return {
                    "probability": 0.5,
                    "confidence": "low",
                    "tier": "POSSIBLE_SPONSOR",
                    "reason": "Model not trained. Run nj ml train first.",
                }

        from scipy.sparse import csr_matrix, hstack

        text = f"{company_name} {job_title}".lower()
        X_tfidf = self.vectorizer.transform([text])

        try:
            state_enc = self.label_encoder.transform([state.upper()])[0]
        except ValueError:
            state_enc = 0

        X_meta = csr_matrix(np.array([[state_enc, year, petition_count]]))
        X = hstack([X_tfidf, X_meta])

        proba = self.model.predict_proba(X)[0]
        prob_positive = float(proba[1])

        if prob_positive >= 0.75:
            confidence = "high"
            tier = "LIKELY_SPONSOR"
        elif prob_positive >= 0.50:
            confidence = "medium"
            tier = "POSSIBLE_SPONSOR"
        else:
            confidence = "low"
            tier = "UNLIKELY_SPONSOR"

        return {
            "probability": round(prob_positive, 3),
            "confidence": confidence,
            "tier": tier,
            "company": company_name,
            "role": job_title,
        }

    def _load_training_data(self, db_path: str) -> tuple[list[str], list[list], list[int]]:
        from sqlalchemy import text as sa_text

        from nj.db.engine import get_engine

        X_text: list[str] = []
        X_meta: list[list] = []
        y: list[int] = []

        engine = get_engine(db_path)
        with engine.connect() as conn:
            rows = conn.execute(
                sa_text(
                    "SELECT employer_name, job_title, "
                    "worksite_state, year, case_status, "
                    "COUNT(*) as cnt "
                    "FROM h1b_petitions "
                    "GROUP BY employer_name, job_title, "
                    "worksite_state, year, case_status "
                    "LIMIT 50000"
                )
            ).fetchall()

        for row in rows:
            employer, title, state, yr, status, cnt = row
            text_feat = f"{employer or ''} {title or ''}".lower()
            X_text.append(text_feat)
            X_meta.append(
                [
                    (state or "CA").upper(),
                    yr or 2024,
                    min(cnt, 100),
                ]
            )
            label = 1 if (status and "certif" in status.lower()) else 0
            y.append(label)

        return X_text, X_meta, y

    def _save(self) -> None:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        if MODEL_PATH.exists():
            MODEL_PATH.unlink()
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(
                {
                    "model": self.model,
                    "vectorizer": self.vectorizer,
                    "label_encoder": self.label_encoder,
                    "training_samples": self.training_samples,
                },
                f,
            )
        logger.info("sponsorship_model_saved", path=str(MODEL_PATH))

    def _load(self) -> bool:
        if not MODEL_PATH.exists():
            return False
        try:
            with open(MODEL_PATH, "rb") as f:
                data = pickle.load(f)
            self.model = data["model"]
            self.vectorizer = data["vectorizer"]
            self.label_encoder = data["label_encoder"]
            self.training_samples = data.get("training_samples", 0)
            self.is_trained = True
            return True
        except Exception as e:
            logger.warning("sponsorship_model_load_failed", error=str(e))
            return False


_sponsorship_model: SponsorshipModel | None = None


def get_sponsorship_model() -> SponsorshipModel:
    global _sponsorship_model
    if _sponsorship_model is None:
        _sponsorship_model = SponsorshipModel()
        _sponsorship_model._load()
    return _sponsorship_model
