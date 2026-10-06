from datetime import timedelta

from sqlalchemy import select

from app.models import AuthSession, User
from app.models.base import utcnow
from tests.conftest import PASSWORD, register


def test_register_creates_user_with_session_cookie(client, session_factory, settings):
    res = register(client, "New.User@Example.com")
    assert res.status_code == 201
    assert res.json()["email"] == "new.user@example.com"  # normalised
    assert "password" not in res.text
    assert settings.session_cookie_name in client.cookies
    set_cookie = res.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie

    with session_factory() as db:
        user = db.scalar(select(User))
        assert user.password_hash != PASSWORD and user.password_hash.startswith("$argon2")
        assert user.profile is not None and user.nutrition_profile is not None


def test_session_token_is_stored_hashed(client, session_factory, settings):
    register(client, "a@example.com")
    token = client.cookies[settings.session_cookie_name]
    with session_factory() as db:
        assert db.scalar(select(AuthSession.token_hash)) != token


def test_duplicate_email_rejected(client, other_client):
    assert register(client, "dup@example.com").status_code == 201
    res = register(other_client, "DUP@example.com")
    assert res.status_code == 409 and res.json()["error"]["code"] == "email_taken"


def test_register_validation(client):
    assert register(client, "not-an-email").status_code == 422
    short = register(client, "a@example.com", "short")
    assert short.status_code == 422
    assert short.json()["error"]["code"] == "validation_error"


def test_login_success_and_failure(client, other_client):
    register(client, "a@example.com")
    ok = other_client.post("/api/auth/login", json={"email": "a@example.com", "password": PASSWORD})
    assert ok.status_code == 200 and other_client.get("/api/auth/me").status_code == 200

    wrong = client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope-nope-nope"})
    unknown = client.post("/api/auth/login", json={"email": "x@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"] == unknown.json()["error"]  # no account enumeration


def test_logout_invalidates_session(alice):
    assert alice.get("/api/auth/me").status_code == 200
    stolen = dict(alice.cookies)
    assert alice.post("/api/auth/logout").status_code == 204
    assert alice.get("/api/auth/me").status_code == 401
    alice.cookies.update(stolen)  # replaying the old cookie must fail server-side
    assert alice.get("/api/auth/me").status_code == 401


def test_expired_session_rejected(alice, session_factory):
    with session_factory() as db:
        s = db.scalar(select(AuthSession))
        s.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    res = alice.get("/api/auth/me")
    assert res.status_code == 401 and res.json()["error"]["code"] == "not_authenticated"


def test_protected_routes_require_login(client):
    for method, path in [
        ("get", "/api/profile"), ("put", "/api/profile"), ("get", "/api/equipment"),
        ("get", "/api/exercises"), ("post", "/api/exercises"), ("get", "/api/workouts"),
        ("get", "/api/workout-sessions"), ("get", "/api/body-metrics"),
        ("get", "/api/nutrition/profile"),
    ]:
        res = getattr(client, method)(path)
        assert res.status_code == 401, path
        assert res.json()["error"]["code"] == "not_authenticated"


def test_cross_origin_writes_blocked(alice):
    res = alice.put("/api/profile", json={"age": 30}, headers={"Origin": "https://evil.example"})
    assert res.status_code == 403
    assert alice.get("/api/profile").json()["age"] is None


def test_security_headers_present(client):
    res = client.get("/api/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert "script-src 'self'" in res.headers["content-security-policy"]
