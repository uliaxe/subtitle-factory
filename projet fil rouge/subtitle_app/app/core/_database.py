from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ._config import SETTINGS


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 30}
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args=connect_args)


ENGINE = _make_engine(SETTINGS.database_url)
SessionLocal = sessionmaker(bind=ENGINE, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import cruds

    Base.metadata.create_all(ENGINE)
