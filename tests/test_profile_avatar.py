import io
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import BASE_DIR
from app.database.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password

client = TestClient(app)

def _get_cookies_for_user(role_name: str):
    db = SessionLocal()
    user = db.query(User).filter(User.role == role_name).first()
    assert user is not None, f"User with role {role_name} not found"
    user.password_hash = hash_password("TestPass123!")
    user_campus = user.campus or "Multan Campus"
    user_ident = user.identifier
    db.commit()
    db.close()

    resp = client.post(
        "/login",
        data={
            "account_type": role_name,
            "campus": user_campus,
            "identifier": user_ident,
            "password": "TestPass123!",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303, f"Login failed with {resp.status_code}: {resp.text}"
    return resp.cookies


def test_student_upload_and_remove_avatar():
    cookies = _get_cookies_for_user("STUDENT")

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        + (b"\x00" * 4000)
    )

    db = SessionLocal()
    stu = db.query(User).filter(User.role == "STUDENT").first()
    db.close()

    # 1. Upload valid avatar
    resp = client.post(
        "/profile/edit",
        data={
            "full_name": stu.full_name,
            "email": stu.email,
            "identifier": stu.identifier,
            "campus": stu.campus or "Multan Campus",
            "program": stu.program or "BS Computer Science",
        },
        files={
            "avatar": ("my_avatar.png", png_bytes, "image/png")
        },
        cookies=cookies,
        follow_redirects=False,
    )
    assert resp.status_code == 303

    db = SessionLocal()
    updated_stu = db.get(User, stu.id)
    assert updated_stu.avatar_path is not None
    assert updated_stu.avatar_path.startswith("/static/uploads/avatars/")
    avatar_disk = Path(BASE_DIR) / "app" / updated_stu.avatar_path.lstrip("/")
    assert avatar_disk.exists()
    db.close()

    # 2. Check profile page renders avatar
    prof_resp = client.get("/student/profile", cookies=cookies)
    assert prof_resp.status_code == 200
    assert updated_stu.avatar_path in prof_resp.text

    # 3. Check dashboard renders avatar
    dash_resp = client.get("/student/dashboard", cookies=cookies)
    assert dash_resp.status_code == 200
    assert updated_stu.avatar_path in dash_resp.text

    # 4. Remove avatar
    remove_resp = client.post(
        "/profile/edit",
        data={
            "full_name": stu.full_name,
            "email": stu.email,
            "identifier": stu.identifier,
            "campus": stu.campus or "Multan Campus",
            "remove_avatar": "1",
        },
        cookies=cookies,
        follow_redirects=False,
    )
    assert remove_resp.status_code == 303

    db = SessionLocal()
    cleared_stu = db.get(User, stu.id)
    assert cleared_stu.avatar_path is None
    assert not avatar_disk.exists()
    db.close()


def test_admin_upload_avatar():
    cookies = _get_cookies_for_user("ADMIN")

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        + (b"\x00" * 4000)
    )

    db = SessionLocal()
    admin_user = db.query(User).filter(User.role == "ADMIN").first()
    db.close()

    resp = client.post(
        "/profile/edit",
        data={
            "full_name": admin_user.full_name,
            "email": admin_user.email,
            "identifier": admin_user.identifier,
            "campus": admin_user.campus or "Multan Campus",
        },
        files={
            "avatar": ("admin_pic.png", png_bytes, "image/png")
        },
        cookies=cookies,
        follow_redirects=False,
    )
    assert resp.status_code == 303

    db = SessionLocal()
    updated_admin = db.get(User, admin_user.id)
    assert updated_admin.avatar_path is not None
    avatar_disk = Path(BASE_DIR) / "app" / updated_admin.avatar_path.lstrip("/")
    assert avatar_disk.exists()

    # Clean up
    if avatar_disk.exists():
        avatar_disk.unlink()
    updated_admin.avatar_path = None
    db.commit()
    db.close()


def test_avatar_oversized_rejected():
    cookies = _get_cookies_for_user("STUDENT")
    oversized = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4" + (b"\x00" * (500 * 1024 + 100))

    db = SessionLocal()
    stu = db.query(User).filter(User.role == "STUDENT").first()
    db.close()

    resp = client.post(
        "/profile/edit",
        data={
            "full_name": stu.full_name,
            "email": stu.email,
            "identifier": stu.identifier,
            "campus": stu.campus or "Multan Campus",
        },
        files={
            "avatar": ("huge.png", oversized, "image/png")
        },
        cookies=cookies,
    )
    assert resp.status_code == 400
    assert "500 KB" in resp.text

