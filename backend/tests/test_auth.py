def test_login_success(client, admin_user):
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"
    assert "password_hash" not in data


def test_login_wrong_password(client, admin_user):
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "nope"},
    )
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "ghost", "password": "x"},
    )
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_me_after_login(client, regular_user, login):
    login(regular_user)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "dana"
    assert resp.get_json()["role"] == "user"


def test_logout_clears_session(client, regular_user, login):
    login(regular_user)
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
