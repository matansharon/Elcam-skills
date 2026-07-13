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
