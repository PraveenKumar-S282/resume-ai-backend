from tests.conftest import PASSWORD, make_user


def test_register_login_me_logout(client):
    make_user(client)
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200 and r.json()["email"] == "asha@example.com"
    assert "password" not in r.text
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_cookie_is_httponly(client):
    client.post("/api/v1/auth/register", json={"full_name": "Asha K", "email": "a@b.com", "password": PASSWORD})
    r = client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": PASSWORD})
    assert "httponly" in r.headers["set-cookie"].lower()


def test_duplicate_email_is_409_case_insensitive(client):
    make_user(client)
    r = client.post("/api/v1/auth/register", json={"full_name": "Other", "email": "ASHA@example.com", "password": PASSWORD})
    assert r.status_code == 409 and r.json()["error"]["code"] == "EMAIL_TAKEN"


def test_wrong_password_is_generic_401(client):
    make_user(client)
    bad_pw = client.post("/api/v1/auth/login", json={"email": "asha@example.com", "password": "nope12345"})
    no_user = client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope12345"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json() == no_user.json()  # does not reveal which emails exist


def test_weak_password_rejected_with_field_details(client):
    r = client.post("/api/v1/auth/register", json={"full_name": "Asha K", "email": "a@b.com", "password": "short"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "VALIDATION_ERROR" and body["details"][0]["field"] == "password"


def test_protected_routes_require_login(client):
    for path in ["/api/v1/profile", "/api/v1/documents", "/api/v1/dashboard/stats", "/api/v1/templates"]:
        assert client.get(path).status_code == 401, path


def test_change_password(client):
    make_user(client)
    assert client.post("/api/v1/auth/change-password", json={"current_password": "wrongpass1", "new_password": "NewPassw0rd1"}).status_code == 400
    assert client.post("/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": "NewPassw0rd1"}).status_code == 204
    client.post("/api/v1/auth/logout")
    assert client.post("/api/v1/auth/login", json={"email": "asha@example.com", "password": "NewPassw0rd1"}).status_code == 200


def test_update_me_email_conflict(client):
    make_user(client, "one@example.com")
    client.post("/api/v1/auth/logout")
    make_user(client, "two@example.com")
    r = client.patch("/api/v1/auth/me", json={"email": "one@example.com"})
    assert r.status_code == 409


def test_delete_account_removes_everything(client, db_session):
    from sqlalchemy import func, select
    from app.models import CandidateProfile, Skill, User

    make_user(client)
    client.post("/api/v1/profile/skills", json={"name": "Python", "category": "language"})
    assert client.delete("/api/v1/auth/me").status_code == 204
    with db_session() as s:
        assert s.scalar(select(func.count()).select_from(User)) == 0
        assert s.scalar(select(func.count()).select_from(CandidateProfile)) == 0
        assert s.scalar(select(func.count()).select_from(Skill)) == 0


def test_foreign_origin_blocked_on_writes(client):
    make_user(client)
    r = client.post("/api/v1/profile/skills", json={"name": "Go"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN_ORIGIN"
    ok = client.post("/api/v1/profile/skills", json={"name": "Go"}, headers={"Origin": "http://localhost:5173"})
    assert ok.status_code == 201
