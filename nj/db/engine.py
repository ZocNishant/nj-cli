from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


# One engine per database file, not one engine per process.
#
# This used to be a single module-level `_engine` guarded by `if _engine is
# None`, which meant the *first* db_path won and every later one was silently
# ignored. In a one-shot CLI invocation that is invisible. In the interactive
# shell — one process, many commands — the second `--db` read and wrote the
# first database, and every repository accepts a db_path while every command
# exposes `--db`, so the abstraction promised something the engine did not
# honour.
#
# Keyed on the resolved absolute path so "data/nj.db" and "./data/nj.db" share
# a pool rather than opening two.
_engines: dict[str, Engine] = {}
_sessionmakers: dict[str, sessionmaker[Session]] = {}
_schema_ready: set[str] = set()


def _key(db_path: str) -> str:
    return str(Path(db_path).expanduser().resolve())


def get_engine(db_path: str = "data/nj.db") -> Engine:
    key = _key(db_path)
    engine = _engines.get(key)
    if engine is None:
        Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{key}", echo=False)
        _engines[key] = engine
        _ensure_schema(engine, key)
    return engine


def _ensure_schema(engine: Engine, key: str) -> None:
    """Create any missing tables, once per database per process.

    Fifteen entry points — `explain`, `status`, `review`, `tailor`, `label`,
    `diff`, the banner, and the rest — build a repository without ever calling
    `init_db`, so on a database that has not been through `nj init` or
    `nj search` they queried a table that did not exist. The single global
    engine hid this in the test suite (the first test to initialise a database
    supplied the schema for every later path), but not from a real operator:
    `nj status` on a fresh clone raised `no such table: applications`.

    Idempotent and metadata-driven, exactly like `init_db` — it creates what is
    missing and never alters what is there, so it cannot fight Alembic.
    """
    if key in _schema_ready:
        return
    from nj.db.models import Base as ModelBase

    ModelBase.metadata.create_all(engine)
    _schema_ready.add(key)


def dispose_engines() -> None:
    """Drop every cached engine and its pool. For tests and long-lived shells."""
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()
    _sessionmakers.clear()
    _schema_ready.clear()


def init_db(db_path: str = "data/nj.db") -> None:
    """Kept as the explicit form. `get_engine` now does this on first use."""
    get_engine(db_path)


def _get_sessionmaker(db_path: str) -> sessionmaker[Session]:
    """Cached per database. Building one per call is pure overhead, and the
    dedup path calls this once per scraped job."""
    key = _key(db_path)
    factory = _sessionmakers.get(key)
    if factory is None:
        factory = sessionmaker(bind=get_engine(db_path))
        _sessionmakers[key] = factory
    return factory


@contextmanager
def get_session(db_path: str = "data/nj.db") -> Generator[Session, None, None]:
    session = _get_sessionmaker(db_path)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
