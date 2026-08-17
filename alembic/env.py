"""Alembic environment for nj-cli.

Two things differ from the generated template.

**The URL comes from the environment, not alembic.ini.** The database path is
per-operator (`NJ_DB_PATH`, defaulting to `data/nj.db`, which is gitignored), so
hardcoding it in a tracked ini file would be wrong for everyone but the author.
It also makes generating a baseline against a scratch database a matter of
setting one variable.

**Batch mode is on.** SQLite cannot ALTER a column; Alembic's `render_as_batch`
emulates it by rebuilding the table. Without it, the first migration that alters
or drops a column fails at runtime rather than at review time.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Importing the models is what populates Base.metadata. Without this import the
# metadata is empty and `--autogenerate` cheerfully emits a migration that drops
# every table.
from nj.db import models as _models  # noqa: F401
from nj.db.engine import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Resolve the database URL.

    `NJ_ALEMBIC_URL` wins when set — that is the escape hatch for pointing at a
    scratch database. Otherwise the same `NJ_DB_PATH` the CLI uses.
    """
    url = os.getenv("NJ_ALEMBIC_URL")
    if url:
        return url
    return f"sqlite:///{os.getenv('NJ_DB_PATH', 'data/nj.db')}"


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    section = config.get_section(config.config_ini_section, {}) or {}
    section["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
