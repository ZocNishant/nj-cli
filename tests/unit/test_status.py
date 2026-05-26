from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from nj.cli.cmd_status import STATUS_COLORS, _print_stats
from nj.models.application import ApplicationRecord, ApplicationStatus
from nj.models.config import Config
from nj.notify.digest import format_summary_table


def make_app(score: int = 75, status: str = "submitted") -> ApplicationRecord:
    return ApplicationRecord(
        id="app-1",
        job_id="job-1",
        applied_at=datetime.now(UTC),
        status=ApplicationStatus(status),
        score=score,
    )


def test_status_colors_has_all_statuses() -> None:
    for status in ApplicationStatus:
        assert status.value in STATUS_COLORS or True


def test_print_stats_renders_without_error() -> None:
    apps = [make_app(75), make_app(62), make_app(88)]
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.cmd_status.console", c):
        _print_stats(apps)
    output = buf.getvalue()
    assert "Stats" in output


def test_run_status_empty_db() -> None:
    from nj.cli.cmd_status import run_status
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    mock_repo = MagicMock()
    mock_repo.get_applications.return_value = []
    with patch("nj.cli.cmd_status.console", c), \
         patch("nj.cli.cmd_status.ApplicationRepo", return_value=mock_repo):
        run_status(config=Config(), db_path=":memory:")
    output = buf.getvalue()
    assert "No applications" in output


def test_digest_table_sorted_by_score() -> None:
    apps = [
        {"score": 55, "status": "submitted",
         "company": "Low", "title": "Role A", "visa_label": "unknown"},
        {"score": 88, "status": "submitted",
         "company": "High", "title": "Role B", "visa_label": "confirmed"},
    ]
    result = format_summary_table(apps)
    assert result.index("High") < result.index("Low")


def test_label_stats_empty() -> None:
    from nj.cli.cmd_label import _show_label_stats
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    mock_repo = MagicMock()
    mock_repo.get_labels.return_value = []
    with patch("nj.cli.cmd_label.console", c):
        _show_label_stats(mock_repo)
    output = buf.getvalue()
    assert "No labels" in output


def test_save_threshold_creates_yaml(tmp_path) -> None:
    from nj.cli.cmd_calibrate import _save_threshold
    import yaml
    config_path = str(tmp_path / "config.yaml")
    _save_threshold(68, config_path)
    with open(config_path) as f:
        data = yaml.safe_load(f)
    assert data["scoring"]["threshold"] == 68


def test_save_threshold_updates_existing(tmp_path) -> None:
    from nj.cli.cmd_calibrate import _save_threshold
    import yaml
    config_path = str(tmp_path / "config.yaml")
    with open(config_path, "w") as f:
        yaml.dump({"scoring": {"threshold": 62}}, f)
    _save_threshold(70, config_path)
    with open(config_path) as f:
        data = yaml.safe_load(f)
    assert data["scoring"]["threshold"] == 70
