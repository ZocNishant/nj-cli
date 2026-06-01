"""Unit tests for nj manual command reference."""
from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from nj.cli.cmd_help_full import COMMAND_REFERENCE, run_manual, _show_command_detail


def test_command_reference_has_expected_commands():
    expected = [
        "search", "enrich", "explain", "diagnose", "gaps", "frame",
        "diff", "postmortem", "intel", "graph", "ml", "prep", "review",
        "status", "calibrate", "watch", "tailor", "update-cv",
        "update-intern", "init", "run", "demo", "logs", "config",
        "quality", "label", "manual",
    ]
    for cmd in expected:
        assert cmd in COMMAND_REFERENCE, f"Missing command: {cmd}"


def test_each_command_has_required_fields():
    for cmd, ref in COMMAND_REFERENCE.items():
        assert "description" in ref, f"{cmd} missing description"
        assert "flags" in ref, f"{cmd} missing flags"
        assert "examples" in ref, f"{cmd} missing examples"
        assert "notes" in ref, f"{cmd} missing notes"
        assert len(ref["description"]) > 10, f"{cmd} description too short"
        assert len(ref["examples"]) >= 1, f"{cmd} needs at least one example"


def test_run_manual_no_command_shows_full_reference():
    from rich.console import Console
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_help_full.console", c):
        run_manual(command=None)
    output = buf.getvalue()
    assert "Intelligence" in output
    assert "Job discovery" in output
    assert "Data & ML" in output
    assert "System" in output


def test_run_manual_specific_command():
    from rich.console import Console
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_help_full.console", c):
        run_manual(command="intel")
    output = buf.getvalue()
    assert "intel" in output.lower()
    assert "USCIS" in output or "H1B" in output or "sync" in output


def test_run_manual_unknown_command():
    from rich.console import Console
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_help_full.console", c):
        run_manual(command="nonexistent_xyz")
    output = buf.getvalue()
    assert "Unknown" in output or "unknown" in output


def test_show_command_detail_renders_flags():
    from rich.console import Console
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_help_full.console", c):
        _show_command_detail("ml")
    output = buf.getvalue()
    assert "train" in output or "predict" in output or "status" in output


def test_show_command_detail_renders_examples():
    from rich.console import Console
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_help_full.console", c):
        _show_command_detail("search")
    output = buf.getvalue()
    assert "nj search" in output or "search" in output


def test_manual_command_registered():
    from nj.cli.app import app
    callback_names = [
        c.callback.__name__ for c in app.registered_commands if c.callback
    ]
    assert "manual" in callback_names


def test_docs_manual_md_exists():
    docs_path = Path(__file__).parent.parent.parent / "docs" / "MANUAL.md"
    assert docs_path.exists(), "docs/MANUAL.md does not exist"


def test_docs_manual_md_has_content():
    docs_path = Path(__file__).parent.parent.parent / "docs" / "MANUAL.md"
    content = docs_path.read_text()
    assert len(content) > 5000, "docs/MANUAL.md is too short"
    assert "## Intelligence" in content
    assert "## Job Discovery" in content
    assert "### intel" in content
    assert "### ml" in content
    assert "nj intel sync" in content
