from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None


def get_engine(db_path: str = "data/nj.db") -> Engine:
    global _engine
    if _engine is None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return _engine


def init_db(db_path: str = "data/nj.db") -> None:
    from nj.db.models import Base as ModelBase

    engine = get_engine(db_path)
    ModelBase.metadata.create_all(engine)


@contextmanager
def get_session(db_path: str = "data/nj.db") -> Generator[Session, None, None]:
    engine = get_engine(db_path)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
