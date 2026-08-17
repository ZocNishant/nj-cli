"""Unit tests for the Career Knowledge Graph."""

from __future__ import annotations


def make_cv() -> dict:
    return {
        "personal": {
            "name": "Test User",
            "work_authorization": "OPT",
            "graduation_date": "December 2026",
        },
        "skills": {
            "ml_frameworks": ["PyTorch", "TensorFlow"],
            "programming_languages": ["Python", "C++"],
        },
        "experience": [
            {
                "id": "moffitt",
                "title": "ML Intern",
                "company": "Moffitt Cancer Center",
                "start": "June 2026",
                "end": "Present",
                "status": "active",
                "bullets": [],
                "tags": ["ml"],
            }
        ],
        "projects": [
            {
                "id": "gastrovision",
                "name": "GastroVision",
                "anchor": True,
                "tech": ["PyTorch", "EfficientNet"],
                "date": "December 2024",
                "bullets": [],
                "priority": 1,
            }
        ],
        "education": [
            {
                "institution": "University of South Dakota",
                "degree": "MS Computer Science",
                "end": "December 2026",
                "courses": [],
            }
        ],
    }


def _fresh_db(tmp_path):
    """Return a fresh db_path with schema created."""
    import nj.db.engine as eng

    eng._engine = None
    db_path = str(tmp_path / "test.db")
    from nj.db.engine import init_db

    init_db(db_path)
    return db_path


# ---------------------------------------------------------------------------
# GraphRepo tests
# ---------------------------------------------------------------------------


def test_graph_repo_create_node(tmp_path):
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    repo = GraphRepo(db_path)
    node_id = repo.get_or_create_node("skill", "PyTorch", source="test")
    assert isinstance(node_id, int)
    assert node_id > 0


def test_graph_repo_idempotent_node(tmp_path):
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    repo = GraphRepo(db_path)
    id1 = repo.get_or_create_node("skill", "PyTorch")
    id2 = repo.get_or_create_node("skill", "PyTorch")
    assert id1 == id2


def test_graph_repo_create_edge(tmp_path):
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    repo = GraphRepo(db_path)
    n1 = repo.get_or_create_node("person", "Test User")
    n2 = repo.get_or_create_node("skill", "PyTorch")
    edge_id = repo.get_or_create_edge(n1, n2, "HAS_SKILL")
    assert edge_id > 0


def test_graph_repo_idempotent_edge(tmp_path):
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    repo = GraphRepo(db_path)
    n1 = repo.get_or_create_node("person", "Test")
    n2 = repo.get_or_create_node("skill", "PyTorch")
    e1 = repo.get_or_create_edge(n1, n2, "HAS_SKILL")
    e2 = repo.get_or_create_edge(n1, n2, "HAS_SKILL")
    assert e1 == e2


def test_graph_repo_get_neighbors(tmp_path):
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    repo = GraphRepo(db_path)
    person = repo.get_or_create_node("person", "Test")
    skill1 = repo.get_or_create_node("skill", "PyTorch")
    skill2 = repo.get_or_create_node("skill", "TensorFlow")
    repo.get_or_create_edge(person, skill1, "HAS_SKILL")
    repo.get_or_create_edge(person, skill2, "HAS_SKILL")
    neighbors = repo.get_neighbors(person, "HAS_SKILL")
    labels = [n["label"] for n in neighbors]
    assert "PyTorch" in labels
    assert "TensorFlow" in labels


def test_graph_repo_stats_empty(tmp_path):
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    repo = GraphRepo(db_path)
    stats = repo.get_graph_stats()
    assert stats["total_nodes"] == 0
    assert stats["total_edges"] == 0


# ---------------------------------------------------------------------------
# GraphBuilder tests
# ---------------------------------------------------------------------------


def test_graph_builder_from_cv(tmp_path):
    from nj.graph.builder import GraphBuilder
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    builder = GraphBuilder(db_path)
    counts = builder.build_from_cv(make_cv())
    assert counts["nodes"] > 0
    assert counts["edges"] > 0
    repo = GraphRepo(db_path)
    stats = repo.get_graph_stats()
    assert stats["total_nodes"] > 0


def test_graph_builder_creates_skill_nodes(tmp_path):
    from nj.graph.builder import GraphBuilder
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    builder = GraphBuilder(db_path)
    builder.build_from_cv(make_cv())
    repo = GraphRepo(db_path)
    skills = repo.get_nodes_by_type("skill")
    skill_labels = [s.label for s in skills]
    assert "PyTorch" in skill_labels
    assert "TensorFlow" in skill_labels


def test_graph_builder_creates_project_nodes(tmp_path):
    from nj.graph.builder import GraphBuilder
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    builder = GraphBuilder(db_path)
    builder.build_from_cv(make_cv())
    repo = GraphRepo(db_path)
    projects = repo.get_nodes_by_type("project")
    assert any(p.label == "GastroVision" for p in projects)


def test_graph_builder_idempotent(tmp_path):
    from nj.graph.builder import GraphBuilder
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    builder = GraphBuilder(db_path)
    cv = make_cv()
    builder.build_from_cv(cv)
    builder.build_from_cv(cv)
    repo = GraphRepo(db_path)
    skills = repo.get_nodes_by_type("skill")
    pytorch_count = sum(1 for s in skills if s.label == "PyTorch")
    assert pytorch_count == 1


def test_graph_normalize(tmp_path):
    from nj.graph.repo import GraphRepo

    db_path = _fresh_db(tmp_path)
    repo = GraphRepo(db_path)
    assert repo.normalize("PyTorch") == "pytorch"
    assert repo.normalize("  ML Engineer  ") == "ml engineer"
