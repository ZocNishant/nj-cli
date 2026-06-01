"""Unit tests for the H1B intelligence pipeline."""
from __future__ import annotations

from nj.intel.pipeline import (
    normalize_company,
    normalize_title,
    is_ml_role,
    parse_wage,
    _parse_uscis_row,
)
from nj.db.repos.intel_repo import _compute_sponsor_tier


# ---------------------------------------------------------------------------
# normalize_company
# ---------------------------------------------------------------------------

def test_normalize_company_strips_inc():
    assert "google" in normalize_company("Google Inc.")


def test_normalize_company_strips_llc():
    result = normalize_company("OpenAI LLC")
    assert "llc" not in result
    assert "openai" in result


def test_normalize_company_lowercases():
    assert normalize_company("AMAZON") == "amazon"


def test_normalize_company_removes_extra_spaces():
    result = normalize_company("  Meta   Platforms  ")
    assert "  " not in result
    assert "meta" in result


# ---------------------------------------------------------------------------
# normalize_title
# ---------------------------------------------------------------------------

def test_normalize_title_lowercases():
    assert normalize_title("Machine Learning Engineer") == "machine learning engineer"


def test_normalize_title_replaces_dashes():
    result = normalize_title("ML/AI Engineer")
    assert "/" not in result


def test_normalize_title_strips_commas():
    result = normalize_title("Senior, Staff Engineer")
    assert "," not in result


# ---------------------------------------------------------------------------
# is_ml_role
# ---------------------------------------------------------------------------

def test_is_ml_role_machine_learning():
    assert is_ml_role("Machine Learning Engineer") is True


def test_is_ml_role_data_scientist():
    assert is_ml_role("Senior Data Scientist") is True


def test_is_ml_role_computer_vision():
    assert is_ml_role("Computer Vision Researcher") is True


def test_is_ml_role_not_ml():
    assert is_ml_role("Software Engineer") is False


def test_is_ml_role_accountant():
    assert is_ml_role("Staff Accountant") is False


# ---------------------------------------------------------------------------
# parse_wage
# ---------------------------------------------------------------------------

def test_parse_wage_integer_string():
    assert parse_wage("120000") == 120_000.0


def test_parse_wage_with_dollar_and_commas():
    assert parse_wage("$150,000") == 150_000.0


def test_parse_wage_none():
    assert parse_wage(None) is None


def test_parse_wage_empty_string():
    assert parse_wage("") is None


def test_parse_wage_non_numeric():
    assert parse_wage("N/A") is None


# ---------------------------------------------------------------------------
# _parse_uscis_row
# ---------------------------------------------------------------------------

def test_parse_uscis_row_valid():
    row = {
        "Employer": "Google LLC",
        "Initial Approval": "120",
        "Initial Denial": "5",
        "Continuing Approval": "80",
        "Continuing Denial": "2",
        "State": "CA",
        "City": "Mountain View",
    }
    result = _parse_uscis_row(row, year=2023, source_file="test.csv")
    assert result is not None
    assert result["employer_name"] == "Google LLC"
    assert result["job_title"] == "H1B Employee"
    assert result["case_status"] == "Certified"
    assert result["year"] == 2023
    assert result["is_ml_role"] is False
    assert result["worksite_state"] == "CA"
    assert result["source_file"] == "test.csv"
    assert result["wage_from"] is None


def test_parse_uscis_row_denied_when_no_approvals():
    row = {
        "Employer": "Tiny Corp",
        "Initial Approval": "0",
        "Initial Denial": "3",
        "Continuing Approval": "0",
        "Continuing Denial": "1",
        "State": "NY",
        "City": "Albany",
    }
    result = _parse_uscis_row(row, year=2022, source_file="test.csv")
    assert result is not None
    assert result["case_status"] == "Denied"


def test_parse_uscis_row_missing_employer_returns_none():
    row = {
        "Employer": "",
        "Initial Approval": "10",
        "Initial Denial": "0",
        "Continuing Approval": "5",
        "Continuing Denial": "0",
        "State": "WA",
        "City": "Seattle",
    }
    result = _parse_uscis_row(row, year=2023, source_file="test.csv")
    assert result is None


def test_parse_uscis_row_zero_total_returns_none():
    row = {
        "Employer": "Ghost Corp",
        "Initial Approval": "0",
        "Initial Denial": "0",
        "Continuing Approval": "0",
        "Continuing Denial": "0",
        "State": "TX",
        "City": "Austin",
    }
    result = _parse_uscis_row(row, year=2024, source_file="test.csv")
    assert result is None


# ---------------------------------------------------------------------------
# _compute_sponsor_tier
# ---------------------------------------------------------------------------

def test_compute_sponsor_tier_strong():
    assert _compute_sponsor_tier(total=500, approval_rate=0.95, ml_count=50) == "STRONG"


def test_compute_sponsor_tier_moderate():
    assert _compute_sponsor_tier(total=50, approval_rate=0.80, ml_count=5) == "MODERATE"


def test_compute_sponsor_tier_weak():
    assert _compute_sponsor_tier(total=8, approval_rate=0.60, ml_count=0) == "WEAK"


def test_compute_sponsor_tier_unknown():
    assert _compute_sponsor_tier(total=2, approval_rate=0.50, ml_count=0) == "UNKNOWN"


def test_compute_sponsor_tier_high_total_low_approval_not_strong():
    # total >= 100 but approval_rate < 0.85 → not STRONG
    tier = _compute_sponsor_tier(total=200, approval_rate=0.70, ml_count=20)
    assert tier != "STRONG"
