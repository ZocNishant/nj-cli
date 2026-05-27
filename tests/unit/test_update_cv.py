from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from nj.cli.cmd_update_cv import EDITABLE_SECTIONS, _show_cv_sections


def make_cv() -> dict:
    return {
        "personal": {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+1 555 0000",
            "linkedin": "linkedin.com/in/test",
            "github": "github.com/test",
            "location": "Test City, SD",
        },
        "summary": "ML engineer with CV focus.",
        "skills": {
            "ml_frameworks": ["PyTorch", "TensorFlow"],
        },
        "research_interests": ["Computer Vision", "Medical Imaging"],
        "soft_skills": ["Communication", "Leadership"],
    }


def test_editable_sections_defined():
    required = ["summary", "skills", "research_interests", "soft_skills", "personal"]
    for s in required:
        assert s in EDITABLE_SECTIONS


def test_show_cv_sections_renders():
    cv = make_cv()
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_update_cv.console", c):
        _show_cv_sections(cv)
    output = buf.getvalue()
    assert "summary" in output
    assert "skills" in output
    assert "personal" in output


def test_show_cv_sections_shows_preview():
    cv = make_cv()
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_update_cv.console", c):
        _show_cv_sections(cv)
    output = buf.getvalue()
    assert "PyTorch" in output
    assert "ML engineer" in output


def test_run_update_cv_no_file(tmp_path, monkeypatch):
    from nj.cli.cmd_update_cv import run_update_cv
    from nj.models.config import Config

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_update_cv.console", c):
        run_update_cv(Config(), show=True)
    assert "cv_base.json" in buf.getvalue()


def test_run_update_cv_show(tmp_path, monkeypatch):
    from nj.cli.cmd_update_cv import run_update_cv
    from nj.models.config import Config

    monkeypatch.chdir(tmp_path)
    cv_dir = tmp_path / "cv"
    cv_dir.mkdir()
    (cv_dir / "cv_base.json").write_text(json.dumps(make_cv()))
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_update_cv.console", c):
        run_update_cv(Config(), show=True)
    output = buf.getvalue()
    assert "summary" in output
    assert "ML engineer" in output


def test_version_defined():
    from nj.cli.app import __version__

    assert __version__ == "1.2.0"
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
