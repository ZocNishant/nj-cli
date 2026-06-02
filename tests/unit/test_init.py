from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from nj.cli.cmd_init import (
    _load_env,
    _test_anthropic,
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


def test_write_config_overwrites_existing(tmp_path):
    config_path = str(tmp_path / "config.yaml")
    _write_config({"scoring": {"threshold": 62}}, config_path)
    _write_config({"scoring": {"threshold": 70}}, config_path)
    with open(config_path) as f:
        data = yaml.safe_load(f)
    assert data["scoring"]["threshold"] == 70


def test_test_anthropic_returns_false_on_exception():
    with patch("anthropic.Anthropic", side_effect=Exception("bad key")):
        result = _test_anthropic("bad-key")
    assert result is False


def test_step_visa_not_needed():
    from nj.cli.cmd_init import _step_visa
    with patch("nj.cli.cmd_init.Confirm.ask", return_value=False):
        result = _step_visa()
    assert result["enabled"] is False
    assert "work_authorization" in result


def test_step_visa_with_sponsorship():
    from nj.cli.cmd_init import _step_visa
    with patch("nj.cli.cmd_init.Confirm.ask", side_effect=[True, True, True]), \
         patch("nj.cli.cmd_init.Prompt.ask", side_effect=["opt", "OPT — open to H1B sponsorship"]):
        result = _step_visa()
    assert result["enabled"] is True
    assert result["status"] == "opt"
    assert result["h1b_future"] is True


def test_step_preferences_parses_keywords():
    from nj.cli.cmd_init import _step_preferences
    with patch("nj.cli.cmd_init.Prompt.ask", return_value="10+ years, Director"):
        result = _step_preferences({"career_field": "software_engineering"})
    assert "10+ years" in result["keywords_exclude"]
    assert "Director" in result["keywords_exclude"]
