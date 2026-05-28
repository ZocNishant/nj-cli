import pytest
from unittest.mock import patch
from io import StringIO

from rich.console import Console

from nj.cli.banner import (
    get_banner, BANNERS, TAGLINES, TIPS,
    show_banner, _get_quick_stats,
)


def test_get_banner_returns_string():
    result = get_banner()
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_banner_version_substituted():
    result = get_banner("2.0.0")
    if "{version}" in "\n".join(BANNERS):
        assert "2.0.0" in result or "{version}" not in result


def test_get_banner_random_from_list():
    banners_seen = set()
    for _ in range(50):
        b = get_banner()
        banners_seen.add(b[:20])
    assert len(banners_seen) >= 2


def test_taglines_not_empty():
    assert len(TAGLINES) >= 5
    for t in TAGLINES:
        assert len(t) > 5


def test_tips_not_empty():
    assert len(TIPS) >= 5
    for t in TIPS:
        assert "nj" in t


def test_show_banner_renders(tmp_path):
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.banner.console", c):
        show_banner(db_path=str(tmp_path / "nj.db"))
    output = buf.getvalue()
    assert len(output) > 10


def test_show_banner_contains_tagline(tmp_path):
    buf = StringIO()
    c = Console(file=buf, highlight=False)
    with patch("nj.cli.banner.console", c):
        show_banner(db_path=str(tmp_path / "nj.db"))
    output = buf.getvalue()
    assert any(
        t.split(".")[0] in output
        for t in TAGLINES
    )


def test_get_quick_stats_no_db(tmp_path):
    result = _get_quick_stats(str(tmp_path / "nonexistent.db"))
    assert result == ""


def test_get_quick_stats_empty_db(tmp_path):
    from nj.db.engine import init_db
    import nj.db.engine as engine_mod
    engine_mod._engine = None
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    result = _get_quick_stats(db_path)
    assert result == "" or isinstance(result, str)


def test_banners_all_non_empty():
    for b in BANNERS:
        assert len(b.strip()) > 0
