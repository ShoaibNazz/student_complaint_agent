"""SQLAlchemy engine and session configuration for the MySQL relational database."""
from __future__ import annotations

from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all relational models."""
    pass


def make_engine(url: str) -> Engine:
    """Create a MySQL SQLAlchemy engine with connection pool pre-ping and recycling."""
    kwargs: dict = {}
    if url.startswith("mysql"):
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 3600
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
    elif url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            from sqlalchemy.pool import StaticPool
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

_tables_initialized = False


def ensure_tables_exist(bind: Engine | None = None) -> None:
    """Safely ensure all database tables exist on demand."""
    global _tables_initialized
    if not _tables_initialized:
        try:
            init_db(bind or engine)
            _tables_initialized = True
        except Exception:
            pass


def get_db() -> Iterator[Session]:
    """Dependency for obtaining a database session."""
    ensure_tables_exist()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind: Engine | None = None) -> None:
    """Initialize the relational schema in MySQL without any dummy or default records."""
    from app import models  # noqa: F401 (registers all models with Base.metadata)
    b = bind or engine
    Base.metadata.create_all(bind=b)
