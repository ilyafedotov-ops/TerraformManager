from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, Optional, Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DB_PATH = Path("data/app.db")

_ENGINES: Dict[Path, Engine] = {}
_SESSIONMAKERS: Dict[Path, sessionmaker[Session]] = {}


def _should_echo_sql() -> bool:
    value = os.getenv("TFM_SQL_ECHO") or os.getenv("SQLALCHEMY_ECHO")
    if not value:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def _normalise_path(db_path: Optional[Path | str]) -> Path:
    if db_path is None:
        path = DEFAULT_DB_PATH
    else:
        path = Path(db_path)
    path = path.expanduser().resolve()
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _create_engine(path: Path) -> Engine:
    return create_engine(
        f"sqlite:///{path}",
        future=True,
        echo=_should_echo_sql(),
        connect_args={"check_same_thread": False},
    )


def get_engine(db_path: Optional[Path | str] = None) -> Engine:
    path = _normalise_path(db_path)
    engine = _ENGINES.get(path)
    if engine is None:
        engine = _create_engine(path)
        _ENGINES[path] = engine
        _SESSIONMAKERS[path] = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return engine


def get_sessionmaker(db_path: Optional[Path | str] = None) -> sessionmaker[Session]:
    path = _normalise_path(db_path)
    engine = _ENGINES.get(path)
    if engine is None:
        engine = get_engine(path)
    return _SESSIONMAKERS[path]


@contextmanager
def session_scope(db_path: Optional[Path | str] = None) -> Iterator[Session]:
    factory = get_sessionmaker(db_path)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_models(db_path: Optional[Path | str] = None) -> None:
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)


def get_session_dependency(db_path: Optional[Path | str] = None) -> Generator[Session, None, None]:
    with session_scope(db_path) as session:
        yield session
