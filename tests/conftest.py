import os

# Must be set before the app is imported so a developer's .env cannot affect tests.
os.environ["AI_PROVIDER"] = "mock"
os.environ["ADMIN_PASSWORD"] = ""
os.environ["AI_RETRY_DELAY"] = "0"
os.environ["REQUIRE_EMAIL"] = "false"
os.environ["REQUIRE_STUDENT_ID"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.ai.factory import set_provider_override
from app.database.database import Base, get_db, make_engine
from app.main import app


@pytest.fixture()
def engine():
    eng = make_engine("sqlite:///:memory:")
    from app import models  # noqa: F401
    Base.metadata.create_all(eng)
    from sqlalchemy.orm import Session as OrmSession
    from app.services.user_service import init_default_users
    with OrmSession(eng) as s:
        init_default_users(s)
    yield eng
    eng.dispose()



@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as session:
        yield session


@pytest.fixture()
def client(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    set_provider_override(None)
    yield TestClient(app)  # no context manager -> lifespan (file DB init) is not run
    app.dependency_overrides.clear()
    set_provider_override(None)


def payload(**over):
    base = {
        "student_name": "Ali Ahmed", "student_id": "STU-1024", "email": "ali@example.edu",
        "class_or_program": "BS Computer Science", "complaint_title": "Assignment marks not uploaded",
        "complaint_text": "My mathematics teacher has not uploaded our assignment marks for the last three weeks.",
    }
    base.update(over)
    return base
