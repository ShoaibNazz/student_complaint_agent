"""SQLAlchemy engine/session setup. Change DATABASE_URL to move to PostgreSQL."""
from __future__ import annotations

from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_db(bind: Engine) -> None:
    from sqlalchemy import inspect, text
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    if "complaints" in tables:
        columns = [c["name"] for c in inspector.get_columns("complaints")]
        if "user_id" not in columns:
            with bind.connect() as conn:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN user_id INTEGER;"))
                conn.commit()
    if "users" in tables:
        user_columns = [c["name"] for c in inspector.get_columns("users")]
        if "admin_id" not in user_columns:
            with bind.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN admin_id VARCHAR(60);"))
                conn.commit()


def init_db(bind: Engine | None = None) -> None:
    from app import models  # noqa: F401  (registers tables)
    b = bind or engine
    Base.metadata.create_all(bind=b)
    _migrate_db(b)
    from app.services.user_service import init_default_users
    with Session(bind=b) as db:
        init_default_users(db)

