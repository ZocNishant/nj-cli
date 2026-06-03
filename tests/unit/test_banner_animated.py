from __future__ import annotations

from unittest.mock import MagicMock, patch

from nj.cli.banner import (
    ANIMATION_STYLES,
    LARGE_BANNERS,
    _bold,
    _color,
    _get_stats_simple,
)


def test_large_banners_not_empty():
    assert len(LARGE_BANNERS) >= 4
    for banner in LARGE_BANNERS:
        assert len(banner) >= 4
        for line in banner:
            assert isinstance(line, str)


def test_animation_styles_defined():
    required = ["scanline", "matrix", "slide", "pulse"]
    for s in required:
        assert s in ANIMATION_STYLES


def test_color_returns_ansi_string():
    result = _color("hello", 0, 200, 255)
    assert "hello" in result
    assert "\033[" in result


def test_bold_returns_ansi_string():
    result = _bold("hello")
    assert "hello" in result
    assert "\033[" in result


def test_get_stats_simple_no_db(tmp_path):
    result = _get_stats_simple(str(tmp_path / "nonexistent.db"))
    assert result["jobs"] == 0
    assert result["applied"] == 0


def test_show_animated_banner_no_crash(tmp_path):
    from nj.cli.banner import show_animated_banner

    with patch("nj.cli.banner._animate_scanline"), patch(
        "nj.cli.banner._animate_matrix_reveal"
    ), patch("nj.cli.banner._animate_slide_in"), patch(
        "nj.cli.banner._animate_pulse"
    ), patch(
        "nj.cli.banner._animate_typing"
    ), patch(
        "time.sleep"
    ):
        show_animated_banner(
            version="1.2.0",
            db_path=str(tmp_path / "nj.db"),
        )


def test_each_animation_callable():
    from nj.cli.banner import (
        _animate_matrix_reveal,
        _animate_pulse,
        _animate_scanline,
        _animate_slide_in,
    )

    banner = LARGE_BANNERS[0]
    with patch("time.sleep"), patch("sys.stdout") as mock_stdout:
        mock_stdout.write = MagicMock()
        mock_stdout.flush = MagicMock()
        _animate_scanline(banner)
        _animate_matrix_reveal(banner)
        _animate_slide_in(banner)
        _animate_pulse(banner, pulses=1)
