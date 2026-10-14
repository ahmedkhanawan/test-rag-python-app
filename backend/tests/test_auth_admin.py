from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import JWT_ALGORITHM, hash_password
from app.main import app
from app.models import Chunk, Conversation, Document, DocumentStatus, Message, MessageRole

SECRET = "x" * 40
PASSWORD = "correct horse battery"


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password(PASSWORD))
    monkeypatch.setenv("JWT_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client, username="admin", password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def auth(client) -> dict:
    return {"Authorization": f"Bearer {login(client).json()['access_token']}"}


def test_hash_is_argon2id_and_not_plaintext():
    h = hash_password(PASSWORD)
    assert h.startswith("$argon2id$") and PASSWORD not in h


def test_login_success_returns_jwt(configured, client):
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    claims = jwt.decode(body["access_token"], SECRET, algorithms=[JWT_ALGORITHM])
    assert claims["sub"] == "admin"


@pytest.mark.parametrize("user,pw", [("admin", "wrong"), ("nobody", PASSWORD), ("", "")])
def test_login_rejects_bad_credentials_with_generic_message(configured, client, user, pw):
    r = login(client, user, pw)
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid username or password"


def test_login_503_when_not_configured(monkeypatch, client):
    for var in ("ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "JWT_SECRET"):
        monkeypatch.setenv(var, "")
    get_settings.cache_clear()
    try:
        assert login(client).status_code == 503
    finally:
        get_settings.cache_clear()


def test_short_jwt_secret_counts_as_not_configured(configured, monkeypatch, client):
    monkeypatch.setenv("JWT_SECRET", "short")
    get_settings.cache_clear()
    assert login(client).status_code == 503


@pytest.mark.parametrize("path", ["/api/documents", "/api/admin/stats"])
def test_admin_routes_require_token(configured, client, path):
    r = client.get(path)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_admin_routes_reject_invalid_expired_and_wrong_secret_tokens(configured, client):
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {"sub": "admin", "exp": now - timedelta(minutes=1)}, SECRET, algorithm=JWT_ALGORITHM
    )
    forged = jwt.encode(
        {"sub": "admin", "exp": now + timedelta(hours=1)}, "y" * 40, algorithm=JWT_ALGORITHM
    )
    other_user = jwt.encode(
        {"sub": "mallory", "exp": now + timedelta(hours=1)}, SECRET, algorithm=JWT_ALGORITHM
    )
    for token in ("garbage", expired, forged, other_user):
        r = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_documents_list_with_status_and_chunk_counts(configured, client, session):
    ready = Document(name="Handbook", filename="h.pdf", status=DocumentStatus.READY)
    ready.chunks = [Chunk(chunk_index=i, text=f"t{i}", page_number=1) for i in range(3)]
    failed = Document(name="Broken", filename="b.pdf", status=DocumentStatus.FAILED)
    session.add_all([ready, failed])
    session.commit()

    r = client.get("/api/documents", headers=auth(client))
    assert r.status_code == 200
    by_name = {d["name"]: d for d in r.json()}
    assert by_name["Handbook"]["status"] == "READY" and by_name["Handbook"]["chunk_count"] == 3
    assert by_name["Broken"]["status"] == "FAILED" and by_name["Broken"]["chunk_count"] == 0


def test_stats_empty_and_populated(configured, client, session):
    r = client.get("/api/admin/stats", headers=auth(client))
    assert r.json() == {
        "documents": 0,
        "documents_by_status": {"PENDING": 0, "PROCESSING": 0, "READY": 0, "FAILED": 0},
        "chunks": 0, "conversations": 0, "messages": 0,
    }

    doc = Document(name="D", filename="d.pdf", status=DocumentStatus.READY)
    doc.chunks = [Chunk(chunk_index=0, text="a", page_number=1)]
    conv = Conversation()
    conv.messages = [Message(role=MessageRole.USER, content="q")]
    session.add_all([doc, conv])
    session.commit()

    body = client.get("/api/admin/stats", headers=auth(client)).json()
    assert body["documents"] == 1 and body["documents_by_status"]["READY"] == 1
    assert (body["chunks"], body["conversations"], body["messages"]) == (1, 1, 1)


def test_chat_and_health_remain_public(client):
    assert client.get("/api/health").status_code == 200
