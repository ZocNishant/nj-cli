"""The migrations must stay in sync with the ORM.

Without this, adding a column to `nj/db/models.py` and forgetting the migration
is invisible until someone runs `alembic upgrade head` on a fresh machine and
gets a schema the code cannot use. `create_all` hides the problem locally,
because it builds tables straight from the metadata and never consults the
migration history at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from alembic import command
from nj.db import models as _models  # noqa: F401  (registers the tables)
from nj.db.engine import Base

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def alembic_config(db_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture
def migrated_db(tmp_path, monkeypatch):
    """A fresh database with every migration applied."""
    db_path = tmp_path / "migrated.db"
    url = f"sqlite:///{db_path}"
    # env.py reads the URL from the environment, so the fixture sets it there
    # rather than relying on the ini value.
    monkeypatch.setenv("NJ_ALEMBIC_URL", url)
    command.upgrade(alembic_config(url), "head")
    return url


def test_migrations_apply_to_a_clean_database(migrated_db) -> None:
    engine = create_engine(migrated_db)
    with engine.connect() as conn:
        tables = set(Base.metadata.tables)
        found = set(conn.dialect.get_table_names(conn))
    assert tables <= found, f"missing after upgrade: {sorted(tables - found)}"


def test_migrations_match_the_orm(migrated_db) -> None:
    """The real assertion: zero drift between head and Base.metadata."""
    engine = create_engine(migrated_db)
    with engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)

    assert diff == [], (
        "The ORM and the migrations have diverged. Generate a migration:\n"
        "  poetry run alembic revision --autogenerate -m '<what changed>'\n"
        "  poetry run ruff format alembic/\n"
        f"Drift: {diff}"
    )


def test_downgrade_is_reversible(migrated_db) -> None:
    """A migration you cannot roll back is a migration you cannot deploy."""
    cfg = alembic_config(migrated_db)
    command.downgrade(cfg, "base")

    engine = create_engine(migrated_db)
    with engine.connect() as conn:
        remaining = set(conn.dialect.get_table_names(conn))
    # alembic_version is bookkeeping and legitimately survives.
    assert remaining - {"alembic_version"} == set()

    command.upgrade(cfg, "head")
