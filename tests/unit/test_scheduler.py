from __future__ import annotations

from unittest.mock import patch

import pytest

from nj.scheduler.manager import NJ_CRON_MARKER, _parse_time, _read_crontab, get_schedule


def test_parse_time_valid() -> None:
    hour, minute = _parse_time("09:30")
    assert hour == 9
    assert minute == 30


def test_parse_time_defaults_on_invalid() -> None:
    hour, minute = _parse_time("invalid")
    assert hour == 8
    assert minute == 0


def test_parse_time_zero() -> None:
    hour, minute = _parse_time("00:00")
    assert hour == 0
    assert minute == 0


def test_get_schedule_returns_none_when_no_schedule() -> None:
    with patch("nj.scheduler.manager.platform.system", return_value="Linux"), patch(
        "nj.scheduler.manager._read_crontab", return_value=""
    ):
        result = get_schedule()
        assert result is None


def test_get_schedule_finds_cron_entry() -> None:
    cron_line = f"0 8 */3 * * /usr/bin/nj run --silent {NJ_CRON_MARKER}"
    with patch("nj.scheduler.manager.platform.system", return_value="Linux"), patch(
        "nj.scheduler.manager._read_crontab", return_value=cron_line
    ):
        result = get_schedule()
        assert result is not None
        assert "cron" in result


def test_set_schedule_zero_calls_remove() -> None:
    with patch("nj.scheduler.manager.remove_schedule") as mock_remove:
        from nj.scheduler.manager import set_schedule

        set_schedule(0)
        mock_remove.assert_called_once()


def test_set_schedule_calls_cron_on_linux() -> None:
    with patch("nj.scheduler.manager.platform.system", return_value="Linux"), patch(
        "nj.scheduler.manager._set_cron"
    ) as mock_cron, patch(
        "nj.scheduler.manager._find_nj_binary", return_value="/usr/bin/nj"
    ):
        from nj.scheduler.manager import set_schedule

        set_schedule(3, "08:00")
        mock_cron.assert_called_once()


def test_set_schedule_calls_launchd_on_macos() -> None:
    with patch("nj.scheduler.manager.platform.system", return_value="Darwin"), patch(
        "nj.scheduler.manager._set_launchd"
    ) as mock_ld, patch(
        "nj.scheduler.manager._find_nj_binary", return_value="/usr/bin/nj"
    ):
        from nj.scheduler.manager import set_schedule

        set_schedule(3, "08:00")
        mock_ld.assert_called_once()
