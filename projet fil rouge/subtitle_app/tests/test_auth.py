def test_login_with_wrong_password_is_rejected(client):
    response = client.post("/api/v1/auth/login", data={"username": "alice", "password": "nope"})
    assert response.status_code == 401


def test_me_returns_the_logged_user(client, alice):
    response = client.get("/api/v1/auth/me", headers=alice)
    assert response.json()["username"] == "alice"
    assert response.json()["role"] == "user"


def test_routes_require_a_token(client):
    assert client.get("/api/v1/jobs").status_code == 401


def test_logout_invalidates_the_token(client, alice):
    client.post("/api/v1/auth/logout", headers=alice)
    assert client.get("/api/v1/auth/me", headers=alice).status_code == 401


def test_user_cannot_reach_admin_routes(client, alice):
    assert client.get("/api/v1/admin/stats", headers=alice).status_code == 403


def test_admin_can_create_a_user(client, admin):
    response = client.post(
        "/api/v1/admin/users", headers=admin, json={"username": "carol", "password": "carol-pass"}
    )
    assert response.status_code == 201
    login = client.post("/api/v1/auth/login", data={"username": "carol", "password": "carol-pass"})
    assert login.status_code == 200


def test_anyone_can_sign_up_as_a_simple_user(client):
    response = client.post("/api/v1/auth/register", json={"username": "dave", "password": "dave-pass"})
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "user"
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/v1/jobs", headers=headers).status_code == 200


def test_sign_up_cannot_grant_admin_role(client):
    response = client.post(
        "/api/v1/auth/register", json={"username": "eve", "password": "eve-pass", "role": "admin"}
    )
    assert response.json()["user"]["role"] == "user"


def test_sign_up_with_taken_username_is_rejected(client):
    response = client.post("/api/v1/auth/register", json={"username": "alice", "password": "whatever"})
    assert response.status_code == 409


def test_duplicate_username_is_rejected(client, admin):
    response = client.post(
        "/api/v1/admin/users", headers=admin, json={"username": "alice", "password": "another"}
    )
    assert response.status_code == 409


def test_healthcheck(client):
    assert client.get("/healthz").json()["status"] == "ok"
