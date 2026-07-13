from app import create_app
from models import ActivityLog, db


def _panel_app(**overrides):
    cfg = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "ADMIN_PANEL_USER": "owner",
        "ADMIN_PANEL_PASSWORD": "s3cret",
    }
    cfg.update(overrides)
    return create_app(cfg)


def test_config_defaults_disable_panel():
    # Base test app (no panel creds) leaves the panel disabled.
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    assert app.config["ADMIN_PANEL_USER"] is None
    assert app.config["ADMIN_PANEL_PASSWORD"] is None
    assert app.config["ACTIVITY_LOG_MAX_ROWS"] is None


def test_config_reads_panel_credentials():
    app = _panel_app(ACTIVITY_LOG_MAX_ROWS=500)
    assert app.config["ADMIN_PANEL_USER"] == "owner"
    assert app.config["ADMIN_PANEL_PASSWORD"] == "s3cret"
    assert app.config["ACTIVITY_LOG_MAX_ROWS"] == 500


def test_activitylog_to_dict_shape():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        row = ActivityLog(
            actor="dana", method="POST", path="/api/skills",
            status_code=201, duration_ms=12, ip_address="127.0.0.1",
            summary="Created skill 'X'", category="skill",
        )
        db.session.add(row)
        db.session.commit()
        d = row.to_dict()
        assert d["actor"] == "dana"
        assert d["method"] == "POST"
        assert d["path"] == "/api/skills"
        assert d["status_code"] == 201
        assert d["duration_ms"] == 12
        assert d["summary"] == "Created skill 'X'"
        assert d["category"] == "skill"
        assert d["user_id"] is None
        assert "timestamp" in d and d["timestamp"].endswith(("+00:00", "Z")) or "T" in d["timestamp"]


def test_request_is_logged_with_raw_fields(client, regular_user, login):
    login(regular_user)
    client.get("/api/skills")
    with client.application.app_context():
        rows = ActivityLog.query.filter_by(path="/api/skills", method="GET").all()
        assert len(rows) == 1
        row = rows[0]
        assert row.actor == "Dana"          # display_name from conftest
        assert row.user_id == regular_user["id"]
        assert row.status_code == 200
        assert row.duration_ms >= 0


def test_anonymous_request_logs_anonymous_actor(client):
    client.get("/api/skills")  # 401, not logged in
    with client.application.app_context():
        row = ActivityLog.query.filter_by(path="/api/skills").first()
        assert row is not None
        assert row.actor == "anonymous"
        assert row.user_id is None
        assert row.status_code == 401


def test_non_api_paths_are_not_logged(client):
    client.get("/")            # SPA route, not /api/*
    with client.application.app_context():
        assert ActivityLog.query.filter_by(path="/").count() == 0


from models import AuditLog


def test_skill_create_sets_readable_summary(client, regular_user, login):
    login(regular_user)
    resp = client.post("/api/skills", json={"name": "PDF Export", "content": "x"})
    assert resp.status_code == 201
    with client.application.app_context():
        row = ActivityLog.query.filter_by(method="POST", path="/api/skills").first()
        assert row.summary == "Created skill 'PDF Export'"
        assert row.category == "skill"
        # Regression: the per-skill audit trail still records the create.
        assert AuditLog.query.filter_by(action="create").count() == 1


def test_failed_login_is_logged_readably(client, admin_user):
    client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    with client.application.app_context():
        row = ActivityLog.query.filter_by(path="/api/auth/login").first()
        assert row.status_code == 401
        assert row.category == "auth"
        assert "Failed login" in row.summary
        assert row.user_id is None


def test_successful_login_is_logged(client, regular_user):
    client.post("/api/auth/login", json={"username": "dana", "password": "dana123"})
    with client.application.app_context():
        row = ActivityLog.query.filter_by(path="/api/auth/login").first()
        assert row.status_code == 200
        assert row.category == "auth"
        assert row.summary == "Signed in"
        assert row.user_id == regular_user["id"]


def test_panel_login_success_and_session():
    app = _panel_app()
    c = app.test_client()
    assert c.get("/api/activity/session").get_json() == {"authenticated": False}
    resp = c.post("/api/activity/login", json={"username": "owner", "password": "s3cret"})
    assert resp.status_code == 200
    assert resp.get_json()["authenticated"] is True
    assert c.get("/api/activity/session").get_json() == {"authenticated": True}
    c.post("/api/activity/logout")
    assert c.get("/api/activity/session").get_json() == {"authenticated": False}


def test_panel_login_wrong_password():
    app = _panel_app()
    c = app.test_client()
    resp = c.post("/api/activity/login", json={"username": "owner", "password": "nope"})
    assert resp.status_code == 401
    assert c.get("/api/activity/session").get_json()["authenticated"] is False


def test_panel_disabled_when_unconfigured():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    c = app.test_client()
    resp = c.post("/api/activity/login", json={"username": "owner", "password": "s3cret"})
    assert resp.status_code == 401


def test_logs_endpoint_requires_panel_auth():
    app = _panel_app()
    c = app.test_client()
    assert c.get("/api/activity/logs").status_code == 401
    c.post("/api/activity/login", json={"username": "owner", "password": "s3cret"})
    assert c.get("/api/activity/logs").status_code == 200


def _seed_rows(app, rows):
    with app.app_context():
        for r in rows:
            db.session.add(ActivityLog(**r))
        db.session.commit()


def _authed_panel():
    app = _panel_app()
    c = app.test_client()
    c.post("/api/activity/login", json={"username": "owner", "password": "s3cret"})
    return app, c


def test_logs_pagination_and_total():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "a", "method": "GET", "path": f"/api/x/{i}", "status_code": 200}
        for i in range(5)
    ])
    resp = c.get("/api/activity/logs?page=1&page_size=2")
    body = resp.get_json()
    # total counts seeded rows plus the login row and this request is logged
    # after the response, so it is not counted here.
    assert body["page"] == 1 and body["page_size"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 5


def test_logs_filter_by_actor_and_category():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "dana", "method": "POST", "path": "/api/skills",
         "status_code": 201, "summary": "Created skill 'X'", "category": "skill"},
        {"actor": "amit", "method": "POST", "path": "/api/auth/login",
         "status_code": 401, "summary": "Failed login for 'amit'", "category": "auth"},
    ])
    only_dana = c.get("/api/activity/logs?actor=dana").get_json()["items"]
    assert all(r["actor"] == "dana" for r in only_dana)
    only_auth = c.get("/api/activity/logs?category=auth").get_json()["items"]
    assert all(r["category"] == "auth" for r in only_auth)


def test_logs_view_readable_only_returns_rows_with_summary():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "a", "method": "GET", "path": "/api/skills", "status_code": 200},
        {"actor": "a", "method": "POST", "path": "/api/skills", "status_code": 201,
         "summary": "Created skill 'X'", "category": "skill"},
    ])
    items = c.get("/api/activity/logs?view=readable").get_json()["items"]
    assert items and all(r["summary"] for r in items)


def test_logs_text_search_and_bad_status():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "a", "method": "GET", "path": "/api/skills/42", "status_code": 200},
    ])
    found = c.get("/api/activity/logs?q=skills/42").get_json()["items"]
    assert any("skills/42" in r["path"] for r in found)
    assert c.get("/api/activity/logs?status=notanint").status_code == 400
