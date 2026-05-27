from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from nj.cli.cmd_demo import _demo_diagnose, _demo_gaps, _demo_score, _demo_summary
from nj.demo.sample_data import SAMPLE_DIAGNOSIS, SAMPLE_GAPS, SAMPLE_JOB, SAMPLE_SCORE


def test_sample_job_has_required_fields() -> None:
    assert "title" in SAMPLE_JOB
    assert "company" in SAMPLE_JOB
    assert "description" in SAMPLE_JOB
    assert "visa_label" in SAMPLE_JOB
    assert SAMPLE_JOB["visa_label"] == "confirmed"


def test_sample_score_has_six_sub_scores() -> None:
    assert len(SAMPLE_SCORE["sub_scores"]) == 6


def test_sample_score_total_matches_weights() -> None:
    subs = SAMPLE_SCORE["sub_scores"]
    computed = round(sum(s["score"] * s["weight"] for s in subs))
    reported = SAMPLE_SCORE["total_score"]
    assert abs(computed - reported) <= 2


def test_sample_diagnosis_has_critical_issues() -> None:
    assert len(SAMPLE_DIAGNOSIS["critical_issues"]) >= 2
    for issue in SAMPLE_DIAGNOSIS["critical_issues"]:
        assert "section" in issue
        assert "issue" in issue
        assert "severity" in issue
        assert "fix" in issue


def test_sample_diagnosis_has_hidden_strengths() -> None:
    assert len(SAMPLE_DIAGNOSIS["hidden_strengths"]) >= 2


def test_sample_gaps_sorted_by_impact() -> None:
    impacts = [g["impact_score"] for g in SAMPLE_GAPS]
    assert impacts == sorted(impacts, reverse=True)


def test_sample_gaps_frequency_reasonable() -> None:
    for gap in SAMPLE_GAPS:
        assert 0 <= gap["frequency_pct"] <= 100


def test_demo_score_renders() -> None:
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_demo.console", c):
        _demo_score()
    output = buf.getvalue()
    assert "Acme AI" in output
    assert "81" in output


def test_demo_diagnose_renders() -> None:
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_demo.console", c):
        _demo_diagnose()
    output = buf.getvalue()
    assert "MODERATE" in output
    assert "recruiter" in output.lower()


def test_demo_gaps_renders() -> None:
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_demo.console", c):
        _demo_gaps()
    output = buf.getvalue()
    assert "MLflow" in output or "mlflow" in output.lower()
    assert "118" in output


def test_demo_summary_renders() -> None:
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_demo.console", c):
        _demo_summary()
    output = buf.getvalue()
    assert "nj init" in output
    assert "nj search" in output
    assert "console.anthropic.com" in output
