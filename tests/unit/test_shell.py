from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from rich.console import Console

from nj.cli.shell import (
    _dispatch, _get_flag, _show_help,
    _render_splash, _print_command_header, _show_success,
    SHELL_COMMANDS, BANNERS, TAGLINES,
)
from nj.models.config import Config


def test_shell_commands_complete():
    required = [
        "search", "run", "review", "explain", "diff",
        "diagnose", "gaps", "status", "help", "exit",
    ]
    for cmd in required:
        assert cmd in SHELL_COMMANDS


def test_banners_list_not_empty():
    assert len(BANNERS) >= 4
    for b in BANNERS:
        assert len(b.strip()) > 0


def test_taglines_list_not_empty():
    assert len(TAGLINES) >= 5


def test_dispatch_exit_returns_false():
    config = Config()
    assert _dispatch("exit", [], config) is False
    assert _dispatch("quit", [], config) is False
    assert _dispatch("q", [], config) is False


def test_dispatch_empty_returns_true():
    config = Config()
    assert _dispatch("", [], config) is True


def test_dispatch_unknown_command():
    config = Config()
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.shell.console", c):
        result = _dispatch("notacommand", [], config)
    assert result is True
    assert "Unknown command" in buf.getvalue()


def test_dispatch_help():
    config = Config()
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.shell.console", c):
        result = _dispatch("help", [], config)
    assert result is True
    output = buf.getvalue()
    assert "search" in output
    assert "diagnose" in output


def test_dispatch_clear():
    config = Config()
    with patch("nj.cli.shell.console") as mock_console:
        result = _dispatch("clear", [], config)
    assert result is True
    mock_console.clear.assert_called_once()


def test_get_flag_found():
    args = ["--job-id", "abc123", "--other", "val"]
    result = _get_flag(args, "--job-id")
    assert result == "abc123"


def test_get_flag_not_found():
    args = ["--other", "val"]
    result = _get_flag(args, "--job-id")
    assert result is None


def test_get_flag_equals_syntax():
    args = ["--job-id=abc123"]
    result = _get_flag(args, "--job-id")
    assert result == "abc123"


def test_show_help_renders():
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.shell.console", c):
        _show_help()
    output = buf.getvalue()
    assert "search" in output
    assert "Intelligence" in output
    assert "exit" in output


def test_render_splash_renders():
    stats = {
        "jobs": 118, "scored": 45,
        "applied": 3, "interviews": 1,
    }
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.shell.console", c):
        _render_splash(stats, "1.2.0")
    output = buf.getvalue()
    assert "118" in output
    assert "1.2.0" in output


def test_render_splash_empty_stats():
    stats = {"jobs": 0, "scored": 0, "applied": 0, "interviews": 0}
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.shell.console", c):
        _render_splash(stats, "1.2.0")


def test_dispatch_search_dry_run():
    config = Config()
    with patch("nj.cli.shell.importlib") as mock_imp:
        mock_module = MagicMock()
        mock_imp.import_module.return_value = mock_module
        mock_module.run_search = MagicMock()
        result = _dispatch("search", ["--dry-run"], config)
    assert result is True


def test_boot_sequence_runs(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda x: None)
    from nj.cli.shell import _boot_sequence
    from io import StringIO
    from rich.console import Console
    from unittest.mock import patch
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.shell.console", c):
        _boot_sequence()
    assert len(buf.getvalue()) > 0


def test_print_command_header_renders():
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.shell.console", c):
        _print_command_header("search")
    output = buf.getvalue()
    assert "search" in output


def test_show_success_known_command():
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.shell.console", c):
        _show_success("search")
    assert "search complete" in buf.getvalue()


def test_show_success_unknown_command():
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.shell.console", c):
        _show_success("review")
    assert "done" in buf.getvalue()
