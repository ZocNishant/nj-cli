from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console

from nj.cli.cmd_diff import (
    _diff_bullet_lists,
    _diff_projects,
    _diff_skills,
    _diff_summary,
    _safe_name,
)
from nj.models.config import Config


def test_diff_summary_no_change():
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        _diff_summary("Same text.", "Same text.")
    assert "No change" in buf.getvalue()


def test_diff_summary_added():
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        _diff_summary("", "New summary added.")
    assert "ADDED" in buf.getvalue()
    assert "New summary" in buf.getvalue()


def test_diff_summary_changed():
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        _diff_summary("Old summary.", "New summary.")
    output = buf.getvalue()
    assert "Old summary" in output
    assert "New summary" in output


def test_diff_skills_removed_category():
    base = {
        "ml_frameworks": ["PyTorch", "TensorFlow"],
        "security_tools": ["Wireshark", "Metasploit"],
    }
    tailored = {
        "ml_frameworks": ["PyTorch", "TensorFlow"],
    }
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        _diff_skills(base, tailored)
    output = buf.getvalue()
    assert "Wireshark" in output or "Metasploit" in output


def test_diff_skills_no_change():
    skills = {"ml_frameworks": ["PyTorch"]}
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        _diff_skills(skills, skills)
    assert "No changes" in buf.getvalue()


def test_diff_bullet_lists_added():
    base = ["Original bullet."]
    tailored = ["Original bullet.", "New added bullet."]
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        _diff_bullet_lists(base, tailored)
    assert "ADDED" in buf.getvalue()
    assert "New added bullet" in buf.getvalue()


def test_diff_bullet_lists_removed():
    base = ["Keep this.", "Remove this."]
    tailored = ["Keep this."]
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        _diff_bullet_lists(base, tailored)
    assert "REMOVED" in buf.getvalue()
    assert "Remove this" in buf.getvalue()


def test_diff_bullet_lists_rewritten():
    base = ["Managed network infrastructure and resolved alerts."]
    tailored = ["Led network infrastructure improvements and resolved alerts."]
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        _diff_bullet_lists(base, tailored)
    output = buf.getvalue()
    assert "REWRITTEN" in output or "Managed" in output or "Led" in output


def test_diff_projects_order_changed():
    base = [
        {"id": "proj1", "name": "First", "bullets": []},
        {"id": "proj2", "name": "Second", "bullets": []},
    ]
    tailored = [
        {"id": "proj2", "name": "Second", "bullets": []},
        {"id": "proj1", "name": "First", "bullets": []},
    ]
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        _diff_projects(base, tailored)
    assert "ORDER CHANGED" in buf.getvalue()


def test_diff_projects_no_change():
    projects = [
        {"id": "p1", "name": "TestVision", "bullets": ["Achieved 95%."]},
    ]
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        _diff_projects(projects, projects)
    assert "No changes" in buf.getvalue()


def test_safe_name_removes_special_chars():
    result = _safe_name("Acme Corp & Partners!")
    assert " " not in result
    assert "&" not in result
    assert len(result) <= 20


def test_run_diff_no_cv(tmp_path, monkeypatch):
    from nj.cli.cmd_diff import run_diff

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_diff.console", c):
        run_diff(Config(), db_path=str(tmp_path / "nj.db"))
    assert "cv_base.json" in buf.getvalue()


def test_renderer_saves_json(tmp_path):
    from nj.tailoring.renderer import render_cv

    template_file = tmp_path / "template.tex"
    template_file.write_text("\\begin{document}%%NAME%%\\end{document}")
    output_dir = tmp_path / "output"
    cv = {
        "personal": {
            "name": "Test User",
            "email": "t@t.com",
            "phone": "555",
            "linkedin": "li/test",
            "github": "gh/test",
            "location": "SD",
        },
        "summary": "",
        "education": [],
        "skills": {},
        "experience": [],
        "projects": [],
        "gap_explanation": None,
        "research_interests": [],
        "memberships": [],
        "certifications": [],
        "soft_skills": [],
    }

    def fake_run(cmd, **kwargs):
        tex = next(a for a in cmd if a.endswith(".tex"))
        Path(tex.replace(".tex", ".pdf")).write_text("pdf")
        return MagicMock(returncode=0, stderr="")

    with patch("nj.tailoring.renderer.subprocess.run", side_effect=fake_run):
        pdf_path = render_cv(
            cv_data=cv,
            template_path=str(template_file),
            output_dir=str(output_dir),
            company="Acme",
            job_title="ML Engineer",
        )

    pdf = Path(pdf_path)
    json_file = pdf.with_suffix(".json")
    assert json_file.exists()
    data = json.loads(json_file.read_text())
    assert data["personal"]["name"] == "Test User"
