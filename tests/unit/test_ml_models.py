"""Unit tests for nj ML models (no H1B data required)."""

from __future__ import annotations

import numpy as np
import pytest

from nj.ml.salary_model import ROLE_CATEGORIES, STATE_TIERS, SalaryModel
from nj.ml.semantic_model import SemanticModel
from nj.ml.sponsorship_model import SponsorshipModel

# ---------------------------------------------------------------------------
# SponsorshipModel
# ---------------------------------------------------------------------------


def test_sponsorship_model_predict_untrained():
    model = SponsorshipModel()
    result = model.predict("Google", "ML Engineer")
    assert "probability" in result
    assert 0.0 <= result["probability"] <= 1.0


def test_sponsorship_model_predict_returns_tier():
    model = SponsorshipModel()
    result = model.predict("Google", "ML Engineer")
    assert "tier" in result or "reason" in result


def test_sponsorship_model_untrained_returns_reason():
    model = SponsorshipModel()
    result = model.predict("Acme", "Data Scientist")
    # Untrained model must explain why
    assert result.get("reason") or result.get("tier")


# ---------------------------------------------------------------------------
# SalaryModel
# ---------------------------------------------------------------------------


def test_salary_model_predict_untrained():
    model = SalaryModel()
    result = model.predict("ML Engineer", "CA")
    assert "predicted_salary" in result


def test_salary_model_role_category_ml():
    model = SalaryModel()
    cat = model._get_role_category("Machine Learning Engineer")
    assert cat == "ml_engineer"


def test_salary_model_role_category_cv():
    model = SalaryModel()
    cat = model._get_role_category("Computer Vision Engineer")
    assert cat == "cv_engineer"


def test_salary_model_role_category_default():
    model = SalaryModel()
    cat = model._get_role_category("Unknown Random Role")
    assert cat == "software_engineer"


def test_salary_model_extract_features():
    model = SalaryModel()
    features = model._extract_features("ML Engineer", "CA", 2024, True)
    assert len(features) == 4
    assert all(isinstance(f, float) for f in features)


def test_salary_model_state_tier_ca():
    assert STATE_TIERS["CA"] > 1.0


def test_salary_model_state_tier_ny_high():
    assert STATE_TIERS["NY"] > 1.0


def test_salary_model_role_category_nlp():
    model = SalaryModel()
    cat = model._get_role_category("NLP Engineer")
    assert cat == "nlp_engineer"


def test_salary_model_role_category_data_scientist():
    model = SalaryModel()
    cat = model._get_role_category("Senior Data Scientist")
    assert cat == "data_scientist"


# ---------------------------------------------------------------------------
# SemanticModel
# ---------------------------------------------------------------------------


def test_semantic_model_cosine_similarity_identical():
    model = SemanticModel()
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0])
    assert model._cosine_similarity(a, b) == pytest.approx(1.0)


def test_semantic_model_cosine_zero_vector():
    model = SemanticModel()
    a = np.array([0.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0])
    assert model._cosine_similarity(a, b) == 0.0


def test_semantic_model_cosine_orthogonal():
    model = SemanticModel()
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert model._cosine_similarity(a, b) == pytest.approx(0.0)


def test_semantic_model_extract_cv_sections():
    model = SemanticModel()
    cv = {
        "skills": {"ml_frameworks": ["PyTorch", "TensorFlow"]},
        "projects": [
            {
                "name": "GastroVision",
                "tech": ["PyTorch"],
                "bullets": ["96% accuracy"],
            }
        ],
        "experience": [],
        "education": [],
        "summary": "ML engineer",
    }
    sections = model._extract_cv_sections(cv)
    assert "skills" in sections
    assert "PyTorch" in sections["skills"]
    assert "projects" in sections
    assert "GastroVision" in sections["projects"]
    assert "summary" in sections


def test_semantic_model_interpret_strong():
    model = SemanticModel()
    assert "Strong" in model._interpret(0.75)


def test_semantic_model_interpret_moderate():
    model = SemanticModel()
    assert "Moderate" in model._interpret(0.55)


def test_semantic_model_interpret_weak():
    model = SemanticModel()
    assert "Weak" in model._interpret(0.40)


def test_semantic_model_interpret_low():
    model = SemanticModel()
    assert "Low" in model._interpret(0.20)


def test_semantic_model_score_without_transformers():
    model = SemanticModel()
    model.is_loaded = False
    cv = {"skills": {"ml": ["PyTorch"]}, "projects": []}
    result = model.score_cv_jd(cv, "PyTorch ML role")
    assert "semantic_score" in result


def test_role_categories_coverage():
    model = SalaryModel()
    test_roles = [
        "Data Scientist",
        "NLP Engineer",
        "ML Engineer",
        "Computer Vision Engineer",
        "Research Scientist",
    ]
    for role in test_roles:
        cat = model._get_role_category(role)
        assert cat in ROLE_CATEGORIES or cat == "software_engineer"
