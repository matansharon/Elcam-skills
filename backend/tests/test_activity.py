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
