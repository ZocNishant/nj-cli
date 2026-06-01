"""Unit tests for nj shell tab completion."""
from __future__ import annotations

import pytest

from nj.cli.shell import NJCompleter, SHELL_COMMANDS


def make_completer() -> NJCompleter:
    return NJCompleter(list(SHELL_COMMANDS.keys()))


def test_completer_completes_command():
    c = make_completer()
    matches = c._get_matches("se")
    assert any("search" in m for m in matches)


def test_completer_completes_exact():
    c = make_completer()
    matches = c._get_matches("exit")
    assert any("exit" in m for m in matches)


def test_completer_no_match():
    c = make_completer()
    matches = c._get_matches("zzz")
    assert matches == []


def test_completer_all_commands_completable():
    c = make_completer()
    for cmd in SHELL_COMMANDS.keys():
        matches = c._get_matches(cmd[:2])
        assert len(matches) >= 1


def test_completer_state_interface():
    c = make_completer()
    first = c.complete("se", 0)
    assert first is not None
    assert "search" in first or "status" in first
    result = c.complete("zzz", 0)
    assert result is None


def test_subcommands_defined_for_key_commands():
    assert "intel" in NJCompleter.SUBCOMMANDS
    assert "graph" in NJCompleter.SUBCOMMANDS
    assert "ml" in NJCompleter.SUBCOMMANDS
    assert "sync" in NJCompleter.SUBCOMMANDS["intel"]
    assert "build" in NJCompleter.SUBCOMMANDS["graph"]
    assert "train" in NJCompleter.SUBCOMMANDS["ml"]


def test_subcommand_completion():
    c = make_completer()
    subs = NJCompleter.SUBCOMMANDS.get("intel", [])
    assert "sync" in subs
    assert "top" in subs
    assert "company" in subs


def test_completer_returns_space_after_command():
    c = make_completer()
    matches = c._get_matches("exi")
    assert any(m.endswith(" ") for m in matches)


def test_all_shell_commands_in_completer():
    c = make_completer()
    for cmd in SHELL_COMMANDS.keys():
        assert cmd in c.commands
