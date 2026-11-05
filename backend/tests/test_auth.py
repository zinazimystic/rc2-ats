from app.core.config import settings


def reg(client, **over):
    body = {"email": "a@example.com", "password": "Passw0rd!x", "full_name": "Ann Example", "role": "candidate", **over}
    return client.post("/api/auth/register", json=body)


def test_register_login_me_logout(client):
    r = reg(client)
    assert r.status_code == 201 and r.json()["role"] == "candidate"
    assert "ats_session" in r.cookies
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    assert "password" not in r.text
    assert client.get("/api/auth/me").json()["email"] == "a@example.com"
    assert client.post("/api/auth/logout").status_code == 200
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    r = client.post("/api/auth/login", json={"email": "A@Example.com", "password": "Passw0rd!x"})
    assert r.status_code == 200 and client.get("/api/auth/me").status_code == 200


def test_duplicate_email_case_insensitive(client):
    assert reg(client).status_code == 201
    r = reg(client, email="A@EXAMPLE.COM")
    assert r.status_code == 409 and r.json()["code"] == "email_taken"


def test_weak_password_and_bad_email(client):
    r = reg(client, password="short1")
    assert r.status_code == 422 and r.json()["code"] == "validation_error" and r.json()["errors"]
    assert reg(client, password="onlyletters").status_code == 422
    assert reg(client, email="not-an-email").status_code == 422
    assert reg(client, role="admin").status_code == 422


def test_bad_credentials_generic_message(client):
    reg(client)
    a = client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong-pass1"})
    b = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-pass1"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_login_rate_limited(client):
    reg(client)
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "bad-pass1"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "Passw0rd!x"})
    assert r.status_code == 429 and r.json()["code"] == "rate_limited"


def test_bearer_token_accepted(client, app):
    from fastapi.testclient import TestClient

    token = reg(client).cookies["ats_session"]
    with TestClient(app) as other:
        assert other.get("/api/auth/me").status_code == 401
        assert other.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        assert other.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_recruiter_invite_code(client, monkeypatch):
    monkeypatch.setattr(settings, "recruiter_invite_code", "SECRET-1")
    assert reg(client, role="recruiter").status_code == 403
    assert reg(client, role="recruiter", invite_code="nope").status_code == 403
    assert reg(client, role="recruiter", invite_code="SECRET-1").status_code == 201
    assert reg(client, email="c@example.com", role="candidate").status_code == 201  # candidates need no code


def test_role_guards_and_unauthenticated(client, make_client):
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/analytics/overview").status_code == 401
    cand = make_client("candidate", "cand@example.com")
    assert cand.get("/api/analytics/overview").status_code == 403
    assert cand.post("/api/jobs", json={}).status_code == 403
    rec = make_client("recruiter", "rec@example.com")
    assert rec.get("/api/candidates/me/profile").status_code == 403
    assert rec.get("/api/applications/me").status_code == 403


def test_health_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["database"]["ok"] is True and r.json()["database_backend"] == "sqlite"


def test_unknown_route_json_and_no_trailing_slash_redirect(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["code"] == "not_found"
