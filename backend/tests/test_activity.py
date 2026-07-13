from app import create_app


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
