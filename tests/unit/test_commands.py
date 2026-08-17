from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import yaml
from rich.console import Console

from nj.models.config import Config


def test_run_logs_no_file(tmp_path, monkeypatch):
    from nj.cli.cmd_logs import run_logs

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_logs.console", c):
        run_logs(Config(), log_file="logs/nj.log")
    assert "No log file" in buf.getvalue()


def test_run_logs_with_file(tmp_path, monkeypatch):
    from nj.cli.cmd_logs import run_logs

    monkeypatch.chdir(tmp_path)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "nj.log"
    log_file.write_text("INFO: test message\nERROR: something failed\n")
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_logs.console", c):
        run_logs(Config(), log_file=str(log_file))
    output = buf.getvalue()
    assert "test message" in output
    assert "something failed" in output


def test_run_config_no_file(tmp_path, monkeypatch):
    from nj.cli.cmd_config import run_config

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_config.console", c):
        run_config(Config(), config_path="config.yaml", show=False)
    assert "not found" in buf.getvalue()


def test_run_config_show(tmp_path, monkeypatch):
    from nj.cli.cmd_config import run_config

    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"scoring": {"threshold": 68}}))
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_config.console", c):
        run_config(Config(), config_path=str(config_path), show=True)
    assert "68" in buf.getvalue()


def test_run_search_no_cv(tmp_path, monkeypatch):
    from nj.cli.cmd_search import run_search

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_search.console", c):
        run_search(Config(), db_path=str(tmp_path / "nj.db"))
    assert "cv_base.json" in buf.getvalue()


def test_run_tailor_no_cv(tmp_path, monkeypatch):
    from nj.cli.cmd_tailor import run_tailor

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_tailor.console", c):
        run_tailor("https://example.com/job", Config(), db_path=str(tmp_path / "nj.db"))
    assert "cv_base.json" in buf.getvalue()


def test_run_update_intern_no_cv(tmp_path, monkeypatch):
    from nj.cli.cmd_update_intern import run_update_intern

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_update_intern.console", c):
        run_update_intern(Config())
    assert "cv_base.json" in buf.getvalue()


def test_run_pipeline_no_cv(tmp_path, monkeypatch):
    from nj.cli.cmd_run import run_pipeline

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_run.console", c):
        run_pipeline(Config(), db_path=str(tmp_path / "nj.db"), dry_run=True)
    assert "cv_base.json" in buf.getvalue()


def test_run_pipeline_daily_limit_reached(tmp_path, monkeypatch):
    from nj.cli.cmd_run import run_pipeline

    monkeypatch.chdir(tmp_path)
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    mock_app_repo = MagicMock()
    mock_app_repo.count_today.return_value = 10
    with (
        patch("nj.cli.cmd_run.console", c),
        patch("nj.db.repos.application_repo.ApplicationRepo", return_value=mock_app_repo),
        patch("nj.db.engine.init_db"),
    ):
        run_pipeline(Config(), db_path=str(tmp_path / "nj.db"))
    assert "Daily limit" in buf.getvalue()
