import io
import os
import tempfile
from pathlib import Path

import pytest

_TMP_DIR = Path(tempfile.mkdtemp(prefix="subtitle_tests_"))
os.environ.update(
    DATABASE_URL=f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}",
    STORAGE_DIR=str(_TMP_DIR / "storage"),
    FAKE_AI_DELAY_S="0",
    ADMIN_USERNAME="admin",
    ADMIN_PASSWORD="admin-pass",
)

from fastapi.testclient import TestClient

from app.core import ENGINE, Base, SessionLocal
from app.main import app
from app.schemas import Role, UserCreate
from app.services import ensure_default_admin, register_user


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        Base.metadata.drop_all(ENGINE)
        Base.metadata.create_all(ENGINE)
        with SessionLocal() as db:
            ensure_default_admin(db)
            register_user(db, UserCreate(username="alice", password="alice-pass", role=Role.USER))
            register_user(db, UserCreate(username="bob", password="bob-pass", role=Role.USER))
        yield test_client


def auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def alice(client):
    return auth_headers(client, "alice", "alice-pass")


@pytest.fixture
def bob(client):
    return auth_headers(client, "bob", "bob-pass")


@pytest.fixture
def admin(client):
    return auth_headers(client, "admin", "admin-pass")


def upload(client, headers, filename="reunion.wav", output_type="text", content=b"fake-media"):
    return client.post(
        "/api/v1/jobs",
        headers=headers,
        files={"file": (filename, io.BytesIO(content))},
        data={"output_type": output_type},
    )
