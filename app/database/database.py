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

    with bind.connect() as conn:
        # 1. Seed Campuses if empty
        if "campuses" in tables:
            count = conn.execute(text("SELECT COUNT(*) FROM campuses;")).scalar() or 0
            if count == 0:
                verified_campuses = [
                    (1, "Township Campus, Lahore (Main Campus)", "UE-LHR-MAIN", "Central Campus & Administrative Hub, College Road, Township, Lahore"),
                    (2, "Lower Mall Campus, Lahore", "UE-LHR-LM", "Historic Lower Mall Campus, Lahore"),
                    (3, "Bank Road Campus, Lahore", "UE-LHR-BR", "Bank Road Campus for Women, Lahore"),
                    (4, "Attock Campus", "UE-ATK", "Attock Constituent Campus, Punjab"),
                    (5, "Dera Ghazi Khan Campus", "UE-DGK", "DG Khan Constituent Campus, Punjab"),
                    (6, "Faisalabad Campus", "UE-FSD", "Faisalabad Constituent Campus, Samanabad, Faisalabad"),
                    (7, "Jauharabad Campus", "UE-JHD", "Jauharabad Constituent Campus, Khushab, Punjab"),
                    (8, "Multan Campus", "UE-MLT", "Multan Constituent Campus, Bosan Road, Multan"),
                    (9, "Vehari Campus", "UE-VHR", "Vehari Constituent Campus, Punjab"),
                ]
                for cid, name, code, desc in verified_campuses:
                    conn.execute(
                        text("INSERT INTO campuses (id, name, code, description, is_active) VALUES (:id, :name, :code, :desc, 1);"),
                        {"id": cid, "name": name, "code": code, "desc": desc}
                    )
                conn.commit()

        # 2. Seed Departments if empty
        if "departments" in tables:
            d_count = conn.execute(text("SELECT COUNT(*) FROM departments;")).scalar() or 0
            if d_count == 0:
                from app.core.config import load_json_config
                try:
                    depts_data = load_json_config("departments")
                    for d in depts_data.get("departments", []):
                        d_name = d.get("name")
                        d_desc = d.get("description", "")
                        if d_name:
                            conn.execute(
                                text("INSERT INTO departments (name, description, campuses_served, is_active) VALUES (:name, :desc, 'All Campuses', 1);"),
                                {"name": d_name, "desc": d_desc}
                            )
                    conn.commit()
                except Exception:
                    pass

        # 3. Complaints table migration
        if "complaints" in tables:
            columns = [c["name"] for c in inspector.get_columns("complaints")]
            complaint_migrations = [
                ("user_id", "INTEGER"),
                ("account_type", "VARCHAR(30)"),
                ("originating_campus", "VARCHAR(120)"),
                ("target_campus", "VARCHAR(120)"),
                ("attachment_path", "VARCHAR(500)"),
                ("attachment_name", "VARCHAR(255)"),
            ]
            for col_name, col_type in complaint_migrations:
                if col_name not in columns:
                    conn.execute(text(f"ALTER TABLE complaints ADD COLUMN {col_name} {col_type};"))
            # Backfill legacy complaints with default campus
            conn.execute(text("UPDATE complaints SET originating_campus = 'Township Campus, Lahore (Main Campus)' WHERE originating_campus IS NULL;"))
            conn.execute(text("UPDATE complaints SET target_campus = 'Township Campus, Lahore (Main Campus)' WHERE target_campus IS NULL;"))
            conn.commit()

        # 4. Users table migration
        if "users" in tables:
            user_columns = [c["name"] for c in inspector.get_columns("users")]
            if "admin_id" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN admin_id VARCHAR(60);"))
            if "role_designation" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN role_designation VARCHAR(120);"))
            if "campus" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN campus VARCHAR(120);"))
            if "campus_id" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN campus_id INTEGER;"))
            # Backfill legacy users with default campus
            conn.execute(text("UPDATE users SET campus = 'Township Campus, Lahore (Main Campus)', campus_id = 1 WHERE campus IS NULL;"))
            conn.commit()

        # 5. University Directory migration
        if "university_directory" in tables:
            dir_columns = [c["name"] for c in inspector.get_columns("university_directory")]
            if "role_designation" not in dir_columns:
                conn.execute(text("ALTER TABLE university_directory ADD COLUMN role_designation VARCHAR(120);"))
            if "campus" not in dir_columns:
                conn.execute(text("ALTER TABLE university_directory ADD COLUMN campus VARCHAR(120);"))
            if "campus_id" not in dir_columns:
                conn.execute(text("ALTER TABLE university_directory ADD COLUMN campus_id INTEGER;"))
            # Backfill legacy directory records with default campus
            conn.execute(text("UPDATE university_directory SET campus = 'Township Campus, Lahore (Main Campus)', campus_id = 1 WHERE campus IS NULL;"))
            conn.commit()


def init_db(bind: Engine | None = None) -> None:
    from app import models  # noqa: F401  (registers tables)
    b = bind or engine
    Base.metadata.create_all(bind=b)
    _migrate_db(b)


