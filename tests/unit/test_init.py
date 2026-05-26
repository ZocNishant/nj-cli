from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from nj.cli.cmd_init import (
    _load_env,
    _setup_schedule,
    _setup_visa,
    _write_config,
    _write_env,
)


def test_load_env_returns_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _load_env()
    assert result == {}


def test_load_env_parses_key_value_pairs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "ANTHROPIC_API_KEY=sk-test\nSMTP_HOST=smtp.gmail.com\n"
    )
    result = _load_env()
    assert result["ANTHROPIC_API_KEY"] == "sk-test"
    assert result["SMTP_HOST"] == "smtp.gmail.com"


def test_load_env_skips_comments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "# this is a comment\nKEY=value\n"
    )
    result = _load_env()
    assert "# this is a comment" not in result
    assert result["KEY"] == "value"


def test_write_env_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_env({"KEY1": "val1", "KEY2": "val2"})
    content = (tmp_path / ".env").read_text()
    assert "KEY1=val1" in content
    assert "KEY2=val2" in content


def test_write_config_creates_yaml(tmp_path):
    config_path = str(tmp_path / "config.yaml")
    _write_config({"scoring": {"threshold": 68}}, config_path)
    with open(config_path) as f:
        data = yaml.safe_load(f)
    assert data["scoring"]["threshold"] == 68


def test_setup_schedule_disabled():
    with patch("nj.cli.cmd_init.Confirm.ask", return_value=False):
        result = _setup_schedule()
    assert result["enabled"] is False
    assert result["every_days"] == 3


def test_setup_schedule_custom_days():
    with patch("nj.cli.cmd_init.Confirm.ask", side_effect=[True]), \
         patch("nj.cli.cmd_init.Prompt.ask", side_effect=["5", "09:00"]):
        result = _setup_schedule()
    assert result["enabled"] is True
    assert result["every_days"] == 5
    assert result["time"] == "09:00"


def test_setup_visa_disabled():
    with patch("nj.cli.cmd_init.Confirm.ask", return_value=False):
        result = _setup_visa()
    assert result["enabled"] is False


def test_setup_visa_opt():
    with patch("nj.cli.cmd_init.Confirm.ask", side_effect=[True, True, True]), \
         patch("nj.cli.cmd_init.Prompt.ask", return_value="OPT"):
        result = _setup_visa()
    assert result["enabled"] is True
    assert result["status"] == "OPT"
    assert result["h1b_future"] is True


def test_test_anthropic_returns_false_on_exception():
    from nj.cli.cmd_init import _test_anthropic
    with patch("anthropic.Anthropic", side_effect=Exception("bad key")):
        result = _test_anthropic("bad-key")
    assert result is False


def test_write_config_overwrites_existing(tmp_path):
    config_path = str(tmp_path / "config.yaml")
    _write_config({"scoring": {"threshold": 62}}, config_path)
    _write_config({"scoring": {"threshold": 70}}, config_path)
    with open(config_path) as f:
        data = yaml.safe_load(f)
    assert data["scoring"]["threshold"] == 70
