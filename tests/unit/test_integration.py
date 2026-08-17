"""Integration tests for graph auto-update, diagnose enrichment, and status summary."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nj.models.job import Job, JobStatus, VisaLabel


def make_job(job_id: str = "job-001", company: str = "OpenAI") -> Job:
    return Job(
        id=job_id,
        title="ML Engineer",
        company=company,
        url="https://example.com",
        description="PyTorch deep learning role",
        location="San Francisco, CA",
        source="remoteok",
        visa_label=VisaLabel.CONFIRMED,
        scraped_at=datetime.now(UTC),
        status=JobStatus.NEW,
        description_hash="abc123",
    )


def _fresh_db(tmp_path):
    import nj.db.engine as eng

    eng._engine = None
    db_path = str(tmp_path / "test.db")
    from nj.db.engine import init_db

    init_db(db_path)
    return db_path


def _seed_person(db_path: str) -> None:
    from nj.graph.builder import GraphBuilder

    builder = GraphBuilder(db_path=db_path)
    builder.build_from_cv(
        {
            "personal": {"name": "Test Candidate"},
            "skills": {"languages": ["Python"]},
            "experience": [],
            "projects": [],
            "education": [],
        }
    )


# ---------------------------------------------------------------------------
# 1. Graph auto-update on application submit (cmd_run integration)
# ---------------------------------------------------------------------------


def test_graph_updated_on_application(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_person(db_path)
    from nj.graph.builder import GraphBuilder
    from nj.graph.repo import GraphRepo

    builder = GraphBuilder(db_path=db_path)
    builder.add_job_application(
        job_title="ML Engineer",
        company="OpenAI",
        score=82,
        matched_skills=["PyTorch", "Python"],
        missing_skills=["Kubernetes"],
        outcome=None,
    )

    repo = GraphRepo(db_path=db_path)
    stats = repo.get_graph_stats()
    assert stats["total_nodes"] > 0
    assert stats["total_edges"] > 0

    company_nodes = repo.get_nodes_by_type("company")
    labels = [n.label.lower() for n in company_nodes]
    assert any("openai" in label for label in labels)


# ---------------------------------------------------------------------------
# 2. Graph outcome update on gmail callback
# ---------------------------------------------------------------------------


def test_graph_outcome_updated_on_callback(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_person(db_path)

    from nj.graph.builder import GraphBuilder

    builder = GraphBuilder(db_path=db_path)
    builder.add_job_application(
        job_title="ML Engineer",
        company="DeepMind",
        score=78,
        matched_skills=["TensorFlow"],
        missing_skills=[],
        outcome="interview",
    )

    from nj.graph.repo import GraphRepo

    repo = GraphRepo(db_path=db_path)
    stats = repo.get_graph_stats()
    assert stats["total_nodes"] > 0
    edge_types = stats.get("edge_types", {})
    assert len(edge_types) > 0


# ---------------------------------------------------------------------------
# 3. _build_graph_context returns string
# ---------------------------------------------------------------------------


def test_build_graph_context_with_data(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_person(db_path)
    from nj.diagnostics.engine import _build_graph_context
    from nj.graph.builder import GraphBuilder

    builder = GraphBuilder(db_path=db_path)
    builder.add_job_application(
        job_title="ML Engineer",
        company="Anthropic",
        score=90,
        matched_skills=["Python", "PyTorch"],
        missing_skills=[],
        outcome=None,
    )

    ctx = _build_graph_context(db_path)
    assert isinstance(ctx, str)
    assert len(ctx) > 0


def test_build_graph_context_empty_db(tmp_path):
    db_path = _fresh_db(tmp_path)
    from nj.diagnostics.engine import _build_graph_context

    ctx = _build_graph_context(db_path)
    assert ctx == ""


# ---------------------------------------------------------------------------
# 4. _build_score_context
# ---------------------------------------------------------------------------


def test_build_score_context_with_scores():
    from nj.diagnostics.engine import _build_score_context

    scores = [
        {"total_score": 80, "sub_scores": []},
        {"total_score": 60, "sub_scores": []},
        {"total_score": 70, "sub_scores": []},
    ]
    result = _build_score_context(scores)
    assert isinstance(result, str)
    assert "70.0" in result
    assert "3" in result


def test_build_score_context_empty():
    from nj.diagnostics.engine import _build_score_context

    result = _build_score_context([])
    assert result == ""


# ---------------------------------------------------------------------------
# 5. diagnosis_v1 build_user_prompt with graph_context
# ---------------------------------------------------------------------------


def test_build_user_prompt_includes_graph_context():
    from nj.prompts.diagnosis_v1 import build_user_prompt

    cv = {"skills": {"languages": ["Python"]}, "experience": []}
    prompt = build_user_prompt(
        cv_base=cv,
        target_roles=["ML Engineer"],
        graph_context="Graph: 5 nodes, 8 edges\nKnown skills: Python, PyTorch",
    )
    assert "CAREER GRAPH CONTEXT:" in prompt
    assert "Graph: 5 nodes" in prompt


def test_build_user_prompt_no_graph_context():
    from nj.prompts.diagnosis_v1 import build_user_prompt

    cv = {"skills": {}, "experience": []}
    prompt = build_user_prompt(cv_base=cv, target_roles=["ML Engineer"])
    assert "CAREER GRAPH CONTEXT:" not in prompt


# ---------------------------------------------------------------------------
# 6. _print_enrichment_summary does not raise
# ---------------------------------------------------------------------------


def test_print_enrichment_summary_no_data(tmp_path):
    db_path = _fresh_db(tmp_path)
    from nj.cli.cmd_status import _print_enrichment_summary

    try:
        _print_enrichment_summary(db_path)
    except Exception as e:
        pytest.fail(f"_print_enrichment_summary raised: {e}")


def test_print_enrichment_summary_with_graph(tmp_path):
    db_path = _fresh_db(tmp_path)
    _seed_person(db_path)
    from nj.cli.cmd_status import _print_enrichment_summary
    from nj.graph.builder import GraphBuilder

    builder = GraphBuilder(db_path=db_path)
    builder.add_job_application(
        job_title="SWE",
        company="Google",
        score=75,
        matched_skills=["Go", "Python"],
        missing_skills=[],
        outcome=None,
    )

    try:
        _print_enrichment_summary(db_path)
    except Exception as e:
        pytest.fail(f"_print_enrichment_summary raised with data: {e}")
