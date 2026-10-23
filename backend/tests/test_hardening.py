"""Error handling, logging, configuration and security boundaries (Milestone 11)."""

import io
import json
import logging

import pytest
from fastapi import params
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.auth import login_limiter
from app.api.deps import require_admin
from app.api.documents import _safe_filename
from app.core.config import ConfigurationError, Settings, check_startup_configuration, get_settings
from app.core.database import get_db
from app.core.logging import JsonFormatter, RequestIdFilter, TextFormatter, redact, request_id_var
from app.core.ratelimit import FailureLimiter
from app.main import app, create_app
from tests.test_auth_admin import PASSWORD, auth, client, configured, login  # noqa: F401
from tests.test_chat_api import answerer  # noqa: F401  (fixture re-export)

SECRET_KEY = "sk-abcdefghijklmnopqrstuvwxyz0123456789"


def depends_on_admin(route: APIRoute) -> bool:
    deps = list(route.dependencies) + list(route.dependant.dependencies)
    return any(
        getattr(d, "call", None) is require_admin or getattr(d, "dependency", None) is require_admin
        for d in deps
    ) or any(isinstance(d, params.Depends) and d.dependency is require_admin for d in route.dependencies)


# --- authorization boundary ----------------------------------------------------

PUBLIC = {("GET", "/api/health"), ("POST", "/api/chat"), ("POST", "/api/auth/login")}


def test_every_api_route_is_admin_protected_except_the_public_allowlist():
    unprotected = set()
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api"):
            for method in route.methods:
                if (method, route.path) not in PUBLIC and not depends_on_admin(route):
                    unprotected.add((method, route.path))
    assert unprotected == set()


def test_protected_routes_reject_missing_and_malformed_authorization(configured, client):  # noqa: F811
    for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}, {"Authorization": "Bearer a.b.c"}):
        r = client.get("/api/documents", headers=headers)
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


# --- consistent errors ---------------------------------------------------------

def test_error_bodies_have_detail_and_request_id(configured, client):  # noqa: F811
    for r in (client.get("/api/nope"), client.get("/api/documents")):
        body = r.json()
        assert isinstance(body["detail"], str)
        assert body["request_id"] == r.headers["x-request-id"]


def test_validation_errors_do_not_echo_submitted_values(configured, client):  # noqa: F811
    secret = "p" * 2000  # over the 1024 cap
    r = client.post("/api/auth/login", json={"username": "admin", "password": secret})
    assert r.status_code == 422
    body = r.json()
    assert body["detail"] == "Invalid request"
    assert body["errors"][0]["loc"] == ["body", "password"]
    assert secret not in r.text and "input" not in body["errors"][0]


def test_oversized_username_and_question_are_rejected(configured, client):  # noqa: F811
    assert client.post("/api/auth/login", json={"username": "u" * 256, "password": "x"}).status_code == 422
    assert client.post("/api/chat", json={"question": "q" * 4001}).status_code == 422


def test_unhandled_exception_returns_generic_500_and_logs_type(configured, client, caplog):  # noqa: F811
    def broken_db():
        raise RuntimeError(f"secret-detail {SECRET_KEY}")
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = broken_db
    try:
        with caplog.at_level(logging.ERROR):
            r = TestClient(app, raise_server_exceptions=False).get(
                "/api/admin/stats", headers=auth(client)
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 500
    assert r.json()["detail"] == "Internal server error"
    assert "secret-detail" not in r.text and SECRET_KEY not in r.text
    assert r.json()["request_id"] == r.headers["x-request-id"]
    assert any("RuntimeError" in rec.getMessage() for rec in caplog.records)


def test_database_errors_do_not_leak_details(configured, client):  # noqa: F811
    class BrokenSession:
        def execute(self, *a, **k):
            raise OperationalError("SELECT secret_table", {}, Exception("/var/lib/secret/app.db locked"))

    def broken_db():
        yield BrokenSession()

    headers = auth(client)
    app.dependency_overrides[get_db] = broken_db
    try:
        r = TestClient(app, raise_server_exceptions=False).get("/api/admin/stats", headers=headers)
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 500 and r.json()["detail"] == "Database error"
    assert "secret" not in r.text


# --- request id, headers, access log --------------------------------------------

def test_request_id_is_propagated_or_replaced(client):  # noqa: F811
    ok = client.get("/api/health", headers={"X-Request-ID": "abc-12345678"})
    assert ok.headers["x-request-id"] == "abc-12345678"
    bad = client.get("/api/health", headers={"X-Request-ID": "bad id with spaces\r\n"})
    assert bad.headers["x-request-id"] != "bad id with spaces" and len(bad.headers["x-request-id"]) == 32


def test_response_headers(client):  # noqa: F811
    assert client.get("/api/health").headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/documents").headers["cache-control"] == "no-store"


def test_access_log_has_path_only_and_no_secrets(client, caplog):  # noqa: F811
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get(f"/api/documents?api_key={SECRET_KEY}", headers={"Authorization": "Bearer abc.def.ghi"})
    messages = [r.getMessage() for r in caplog.records if r.name == "app.access"]
    assert messages and "/api/documents" in messages[0] and "401" in messages[0]
    assert "api_key" not in caplog.text and SECRET_KEY not in caplog.text and "abc.def" not in caplog.text


# --- login throttling -------------------------------------------------------------

def test_login_is_throttled_after_repeated_failures(configured, client):  # noqa: F811
    for _ in range(5):
        assert login(client, password="wrong").status_code == 401
    blocked = login(client, password="wrong")
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0
    # even the right password is refused while locked out
    assert login(client).status_code == 429


def test_successful_login_clears_the_failure_count(configured, client):  # noqa: F811
    for _ in range(4):
        login(client, password="wrong")
    assert login(client).status_code == 200
    for _ in range(4):
        assert login(client, password="wrong").status_code == 401


def test_failure_limiter_window_expires():
    now = [0.0]
    limiter = FailureLimiter(clock=lambda: now[0])
    for _ in range(3):
        limiter.record_failure("ip", 60)
    assert limiter.retry_after("ip", 3, 60) > 0
    assert limiter.retry_after("other", 3, 60) == 0
    now[0] = 61
    assert limiter.retry_after("ip", 3, 60) == 0


def test_login_failure_logs_neither_username_nor_password(configured, client, caplog):  # noqa: F811
    with caplog.at_level(logging.INFO):
        login(client, username="alice-typed-password", password="hunter2-secret")
    assert "hunter2-secret" not in caplog.text and "alice-typed-password" not in caplog.text
    assert "Failed admin login" in caplog.text


# --- uploads ------------------------------------------------------------------------

def test_oversized_upload_is_refused_before_parsing(configured, client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    try:
        big = b"%PDF-" + b"0" * (3 * 1024 * 1024)
        r = client.post("/api/documents/upload", files={"file": ("big.pdf", big)}, headers=auth(client))
    finally:
        get_settings.cache_clear()
    assert r.status_code == 413 and "1 MB" in r.json()["detail"]


def test_upload_without_content_length_is_411(configured, client):  # noqa: F811
    def body():
        yield b"--x\r\n"

    r = client.post(
        "/api/documents/upload", content=body(),
        headers={**auth(client), "Content-Type": "multipart/form-data; boundary=x"},
    )
    assert r.status_code == 411


@pytest.mark.parametrize("raw,expected", [
    ("Policy.pdf", "Policy.pdf"),
    ("../../etc/passwd.pdf", "passwd.pdf"),
    ("C:\\Users\\me\\Handbook.PDF", "Handbook.pdf"),
    ("bad\x00na\nme.pdf", "badname.pdf"),
    ("...pdf", "document.pdf"),
    (".pdf", "document.pdf"),
    ("notes.txt", ""),
    ("", ""),
    (None, ""),
    (("a" * 400) + ".pdf", ("a" * 251) + ".pdf"),
])
def test_safe_filename(raw, expected):
    assert _safe_filename(raw) == expected


# --- CORS -------------------------------------------------------------------------------

def test_cors_is_off_by_default(client):  # noqa: F811
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_allows_only_configured_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com/, http://localhost:5173")
    get_settings.cache_clear()
    try:
        cors_client = TestClient(create_app())
    finally:
        get_settings.cache_clear()
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization"}
    ok = cors_client.options("/api/chat", headers={"Origin": "https://app.example.com", **preflight})
    assert ok.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-credentials" not in ok.headers
    other = cors_client.options("/api/chat", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in other.headers


@pytest.mark.parametrize("value", ["*", "example.com", "https://a.example/path"])
def test_invalid_cors_origins_fail_startup(monkeypatch, value):
    monkeypatch.setenv("CORS_ORIGINS", value)
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigurationError, match="CORS_ORIGINS"):
            get_settings()
    finally:
        get_settings.cache_clear()


# --- environment configuration -------------------------------------------------------------

def make_settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_production_without_secrets_fails_with_names_not_values():
    s = make_settings(environment="production", jwt_secret="too-short-secret-value", admin_username="admin")
    with pytest.raises(ConfigurationError) as exc:
        check_startup_configuration(s)
    message = str(exc.value)
    for name in ("OPENAI_API_KEY", "ADMIN_PASSWORD_HASH", "JWT_SECRET"):
        assert name in message
    assert "too-short-secret-value" not in message


def test_production_with_complete_configuration_starts():
    s = make_settings(
        environment="production", openai_api_key=SECRET_KEY, admin_username="admin",
        admin_password_hash="$argon2id$v=19$m=65536,t=3,p=4$abc$def", jwt_secret="j" * 40,
    )
    assert check_startup_configuration(s) == []


def test_development_only_warns():
    problems = check_startup_configuration(make_settings(environment="development"))
    assert any("JWT_SECRET" in p for p in problems)


def test_non_argon2_admin_hash_is_flagged():
    s = make_settings(admin_username="a", admin_password_hash="plaintext-password", jwt_secret="j" * 40, openai_api_key="k")
    assert any("not an Argon2 hash" in p for p in s.problems())


def test_invalid_values_are_reported_by_variable_without_the_value(monkeypatch):
    monkeypatch.setenv("CHUNK_SIZE", "100")
    monkeypatch.setenv("CHUNK_OVERLAP", "500")
    monkeypatch.setenv("ENVIRONMENT", "staging-secret-name")
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigurationError) as exc:
            get_settings()
    finally:
        get_settings.cache_clear()
    assert "ENVIRONMENT" in str(exc.value) and "staging-secret-name" not in str(exc.value)


def test_secrets_are_masked_in_repr():
    s = make_settings(openai_api_key=SECRET_KEY, jwt_secret="j" * 40, admin_password_hash="$argon2id$secret")
    text = repr(s) + str(s)
    assert SECRET_KEY not in text and "j" * 40 not in text and "$argon2id$secret" not in text


# --- logging --------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,leaked", [
    (f"key {SECRET_KEY} used", SECRET_KEY),
    ("Authorization: Bearer abc123.def456", "abc123.def456"),
    ("token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhIn0.c2lnbmF0dXJl", "eyJhbGciOiJIUzI1NiJ9"),
    ("hash $argon2id$v=19$m=65536,t=3,p=4$c2FsdA$aGFzaA done", "c2FsdA"),
    ('password="hunter2" and api_key: abcdef', "hunter2"),
])
def test_redaction(raw, leaked):
    assert leaked not in redact(raw)


def make_record(msg="hello %s", args=("world",), exc_info=None):
    return logging.LogRecord("app.test", logging.INFO, __file__, 1, msg, args, exc_info)


def test_json_formatter_emits_structured_redacted_lines():
    record = make_record(f"called with {SECRET_KEY}", ())
    RequestIdFilter().filter(record)
    token = request_id_var.set("req-123")
    try:
        RequestIdFilter().filter(record)
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert entry["level"] == "INFO" and entry["logger"] == "app.test" and entry["request_id"] == "req-123"
    assert SECRET_KEY not in json.dumps(entry)


def test_tracebacks_are_redacted():
    try:
        raise ValueError(f"boom {SECRET_KEY}")
    except ValueError:
        import sys
        record = make_record("failed", (), sys.exc_info())
    RequestIdFilter().filter(record)
    assert SECRET_KEY not in TextFormatter("%(message)s").format(record)
    assert SECRET_KEY not in JsonFormatter().format(record)


# --- chat rate limit ---------------------------------------------------------------

@pytest.fixture
def chat_client(engine, answerer):  # noqa: F811
    """TestClient wired to an in-memory DB and the fake answerer from test_chat_api."""
    from sqlalchemy.orm import sessionmaker

    from app.api.deps import get_answerer

    factory = sessionmaker(bind=engine)

    def override_db():
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_answerer] = lambda: answerer
    yield TestClient(app)
    app.dependency_overrides.clear()


def set_chat_limit(monkeypatch, requests, window=60):
    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", str(requests))
    monkeypatch.setenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", str(window))
    get_settings.cache_clear()


def test_chat_is_rate_limited_per_client_with_safe_429(monkeypatch, chat_client, answerer):
    set_chat_limit(monkeypatch, 3)
    try:
        codes = [chat_client.post("/api/chat", json={"question": "hi"}).status_code for _ in range(5)]
        blocked = chat_client.post("/api/chat", json={"question": "hi"})
    finally:
        get_settings.cache_clear()
    assert codes == [200, 200, 200, 429, 429]
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many requests. Please wait a moment and try again."
    assert int(blocked.headers["retry-after"]) > 0 and "request_id" in blocked.json()
    assert len(answerer.calls) == 3  # blocked requests never reach the RAG pipeline


def test_chat_rate_limit_is_per_client_and_zero_disables(monkeypatch, chat_client):
    from app.api.chat import chat_limiter

    set_chat_limit(monkeypatch, 1)
    try:
        assert chat_limiter.hit("1.1.1.1", 1, 60) == 0
        assert chat_limiter.hit("1.1.1.1", 1, 60) > 0
        assert chat_limiter.hit("2.2.2.2", 1, 60) == 0  # another client is unaffected
        monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", "0")
        get_settings.cache_clear()
        codes = {chat_client.post("/api/chat", json={"question": "q"}).status_code for _ in range(30)}
        assert codes == {200}
    finally:
        get_settings.cache_clear()


def test_hit_does_not_count_rejected_requests_and_window_expires():
    now = [0.0]
    limiter = FailureLimiter(clock=lambda: now[0])
    assert [limiter.hit("ip", 2, 60) for _ in range(2)] == [0, 0]
    assert limiter.hit("ip", 2, 60) > 0
    now[0] = 30
    assert limiter.hit("ip", 2, 60) > 0  # still inside the first window
    now[0] = 61
    assert limiter.hit("ip", 2, 60) == 0  # the old events have aged out
