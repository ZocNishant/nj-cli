"""The engine cache must respect db_path, and any path must be usable cold.

Both properties were broken together and hid each other. `get_engine` memoised
a single module-level engine, so the first database won and every later
`db_path` was silently ignored; that in turn meant the first test to build a
schema supplied it to every other path, which masked fifteen commands that
query the database without ever creating it.
"""

from __future__ import annotations

import sqlite3

from nj.db.engine import dispose_engines, get_engine, get_session
from nj.db.models import JobORM


def test_two_paths_get_two_engines(tmp_path) -> None:
    a = get_engine(str(tmp_path / "a.db"))
    b = get_engine(str(tmp_path / "b.db"))
    assert a is not b
    assert "a.db" in str(a.url)
    assert "b.db" in str(b.url)


def test_same_path_reuses_one_engine(tmp_path) -> None:
    p = str(tmp_path / "same.db")
    assert get_engine(p) is get_engine(p)


def test_equivalent_paths_share_an_engine(tmp_path) -> None:
    """'./x.db' and 'x.db' are one database and must not open two pools."""
    direct = get_engine(str(tmp_path / "x.db"))
    indirect = get_engine(str(tmp_path / "." / "x.db"))
    assert direct is indirect


def test_a_write_does_not_leak_into_the_other_database(tmp_path) -> None:
    """The bug, stated as an assertion: the second --db was the first one."""
    first = str(tmp_path / "first.db")
    second = str(tmp_path / "second.db")

    get_engine(first)
    with get_session(second) as session:
        session.add(
            JobORM(
                id="only-in-second",
                title="ML Engineer",
                company="Acme",
                url="https://example.com/1",
                description="d",
                location="Remote",
                source="test",
                visa_label="unknown",
                scraped_at=__import__("datetime").datetime(2026, 1, 1),
                status="new",
                description_hash="h",
            )
        )

    with get_session(first) as session:
        assert session.get(JobORM, "only-in-second") is None
    with get_session(second) as session:
        assert session.get(JobORM, "only-in-second") is not None


def test_a_cold_database_has_its_schema(tmp_path) -> None:
    """`nj status` on a fresh clone raised 'no such table: applications'."""
    path = str(tmp_path / "cold.db")
    get_engine(path)

    conn = sqlite3.connect(path)
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()

    for table in ("jobs", "score_results", "applications", "job_enrichments"):
        assert table in names


def test_dispose_releases_everything(tmp_path) -> None:
    path = str(tmp_path / "disposed.db")
    before = get_engine(path)
    dispose_engines()
    assert get_engine(path) is not before
