from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from nj.cli.cmd_frame import _list_projects, _select_project
from nj.models.config import Config
from nj.prompts.frame_v1 import AUDIENCE_PROFILES, PROMPT_VERSION, build_user_prompt


def make_project() -> dict:
    return {
        "id": "gastrovision",
        "name": "GastroVision",
        "anchor": True,
        "tech": ["PyTorch", "EfficientNet", "ViT", "Grad-CAM"],
        "date": "December 2024",
        "priority": 1,
        "tags": ["ml", "computer_vision", "medical_imaging"],
        "bullets": [
            "Achieved 96.11% accuracy on gastrointestinal disease classification.",
            "Resolved 73:1 class imbalance using weighted Cross-Entropy loss.",
            "Applied Grad-CAM for model interpretability.",
        ],
    }


def make_frame_response() -> dict:
    return {
        "audience": "production_ml",
        "framing_angle": "Engineering reliability and deployment readiness",
        "reframed_bullets": [
            "Shipped ensemble classifier achieving 96.11% accuracy on 4-class medical image dataset.",
            "Solved 73:1 class imbalance with weighted loss — production-ready without data collection.",
            "Integrated Grad-CAM for explainability — supports clinical validation workflow.",
        ],
        "reframed_summary": (
            "Built and validated a production-quality medical image classifier "
            "with clinical interpretability baked in."
        ),
        "what_changed": (
            "Shifted from research framing (accuracy benchmarks) to engineering framing "
            "(shipped, production-ready, reliability)."
        ),
        "what_to_emphasize_verbally": (
            "The Grad-CAM integration is not just academic — it is what would let "
            "a clinician trust the model output."
        ),
        "warnings": ["No deployment mentioned — flag if asked about production scale"],
    }


def test_prompt_version() -> None:
    assert PROMPT_VERSION == "frame_v1"


def test_audience_profiles_complete() -> None:
    required = [
        "production_ml",
        "research_lab",
        "healthtech_startup",
        "big_tech",
        "early_stage_startup",
        "custom",
    ]
    for r in required:
        assert r in AUDIENCE_PROFILES


def test_build_user_prompt_includes_project() -> None:
    prompt = build_user_prompt(make_project(), "production_ml")
    assert "GastroVision" in prompt
    assert "96.11" in prompt
    assert "production_ml" in prompt


def test_build_user_prompt_custom_includes_role() -> None:
    prompt = build_user_prompt(
        make_project(),
        "custom",
        role_description="Healthcare AI startup building FDA-cleared tools",
    )
    assert "FDA-cleared" in prompt


def test_build_user_prompt_all_audiences() -> None:
    for audience in AUDIENCE_PROFILES:
        prompt = build_user_prompt(make_project(), audience)
        assert audience in prompt
        assert "GastroVision" in prompt


def test_select_project_by_id() -> None:
    projects = [
        make_project(),
        {"id": "other", "name": "Other", "anchor": False, "tech": [], "bullets": [], "priority": 2},
    ]
    result = _select_project(projects, "gastrovision")
    assert result["id"] == "gastrovision"


def test_select_project_missing_id() -> None:
    projects = [make_project()]
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_frame.console", c):
        result = _select_project(projects, "nonexistent")
    assert result is None
    assert "not found" in buf.getvalue()


def test_select_project_defaults_to_anchor() -> None:
    projects = [
        {"id": "first", "name": "First", "anchor": False, "tech": [], "bullets": [], "priority": 2},
        make_project(),
    ]
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_frame.console", c):
        result = _select_project(projects, None)
    assert result["anchor"] is True


def test_list_projects_shows_anchor() -> None:
    projects = [make_project()]
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_frame.console", c):
        _list_projects(projects)
    output = buf.getvalue()
    assert "gastrovision" in output
    assert "GastroVision" in output


def test_run_frame_no_cv(tmp_path, monkeypatch) -> None:
    from nj.cli.cmd_frame import run_frame

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_frame.console", c):
        run_frame(Config())
    assert "cv_base.json" in buf.getvalue()


def test_run_frame_list_projects(tmp_path, monkeypatch) -> None:
    from nj.cli.cmd_frame import run_frame

    monkeypatch.chdir(tmp_path)
    cv_path = tmp_path / "cv"
    cv_path.mkdir()
    (cv_path / "cv_base.json").write_text(
        json.dumps({"projects": [make_project()], "personal": {"name": "Test"}})
    )
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_frame.console", c):
        run_frame(Config(), list_projects=True)
    assert "GastroVision" in buf.getvalue()
