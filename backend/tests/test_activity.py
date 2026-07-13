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


def test_logs_invalid_date_from():
    app, c = _authed_panel()
    resp = c.get("/api/activity/logs?date_from=notadate")
    assert resp.status_code == 400


def test_logs_invalid_date_to():
    app, c = _authed_panel()
    resp = c.get("/api/activity/logs?date_to=2026-13-99")
    assert resp.status_code == 400


def test_logs_q_matches_summary():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "a", "method": "POST", "path": "/api/skills",
         "status_code": 201, "summary": "Created skill 'DataAnalyzer'"},
    ])
    # Search for a term in summary that is NOT in the path
    found = c.get("/api/activity/logs?q=DataAnalyzer").get_json()["items"]
    assert any("DataAnalyzer" in r["summary"] for r in found)


def test_logs_method_filter_case_insensitive():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "a", "method": "POST", "path": "/api/x", "status_code": 201},
        {"actor": "b", "method": "GET", "path": "/api/y", "status_code": 200},
    ])
    # Lowercase 'post' should match uppercase 'POST'
    posts = c.get("/api/activity/logs?method=post").get_json()["items"]
    assert all(r["method"] == "POST" for r in posts)
    assert len(posts) > 0
    # 'get' should not return POST rows
    gets = c.get("/api/activity/logs?method=get").get_json()["items"]
    assert not any(r["method"] == "POST" for r in gets)


def test_logs_page_clamping():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "a", "method": "GET", "path": f"/api/x/{i}", "status_code": 200}
        for i in range(5)
    ])
    # page=0 should be clamped to 1
    resp = c.get("/api/activity/logs?page=0&page_size=2").get_json()
    assert resp["page"] == 1
    # page_size=500 should be clamped to 200
    resp = c.get("/api/activity/logs?page_size=500").get_json()
    assert resp["page_size"] == 200
    # page_size=0 should be clamped to 1
    resp = c.get("/api/activity/logs?page_size=0").get_json()
    assert resp["page_size"] == 1


def test_logs_non_integer_page_returns_400():
    app, c = _authed_panel()
    resp = c.get("/api/activity/logs?page=abc")
    assert resp.status_code == 400


def test_logs_non_integer_page_size_returns_400():
    app, c = _authed_panel()
    resp = c.get("/api/activity/logs?page_size=xyz")
    assert resp.status_code == 400


def test_logs_ordering_newest_first():
    from datetime import datetime, timedelta
    app, c = _authed_panel()
    base_time = datetime(2026, 7, 13, 10, 0, 0)
    _seed_rows(app, [
        {"actor": "a", "method": "GET", "path": "/api/x/1", "status_code": 200,
         "timestamp": base_time},
        {"actor": "a", "method": "GET", "path": "/api/x/2", "status_code": 200,
         "timestamp": base_time + timedelta(seconds=1)},
        {"actor": "a", "method": "GET", "path": "/api/x/3", "status_code": 200,
         "timestamp": base_time + timedelta(seconds=2)},
    ])
    items = c.get("/api/activity/logs?page_size=100").get_json()["items"]
    # Find the seeded rows (path contains /api/x/)
    seeded = [r for r in items if "/api/x/" in r["path"]]
    # Last seeded row should come first (newest)
    assert seeded[0]["path"] == "/api/x/3"
    assert seeded[1]["path"] == "/api/x/2"
    assert seeded[2]["path"] == "/api/x/1"


def test_stats_shape_and_counts():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "dana", "method": "POST", "path": "/api/skills",
         "status_code": 201, "summary": "Created skill 'X'", "category": "skill"},
        {"actor": "dana", "method": "GET", "path": "/api/skills", "status_code": 200},
        {"actor": "amit", "method": "GET", "path": "/api/skills", "status_code": 200},
    ])
    stats = c.get("/api/activity/stats").get_json()
    assert stats["total"] >= 3
    assert stats["active_users"] >= 2          # dana, amit (plus "owner" login row)
    cats = {row["category"]: row["count"] for row in stats["by_category"]}
    assert cats.get("skill", 0) >= 1
    assert "request" in cats                    # the null-category GET rows
    methods = {row["method"]: row["count"] for row in stats["by_method"]}
    assert methods.get("GET", 0) >= 2
    assert isinstance(stats["timeline"], list) and stats["timeline"]
    assert set(stats["timeline"][0].keys()) == {"bucket", "count"}


def test_stats_honors_actor_filter():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "dana", "method": "GET", "path": "/api/skills", "status_code": 200},
        {"actor": "amit", "method": "GET", "path": "/api/skills", "status_code": 200},
    ])
    stats = c.get("/api/activity/stats?actor=dana").get_json()
    assert stats["active_users"] == 1


def test_export_csv_contains_rows_and_escapes():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "dana", "method": "POST", "path": "/api/skills", "status_code": 201,
         "summary": 'Created skill "X, the great"', "category": "skill"},
    ])
    resp = c.get("/api/activity/export.csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "attachment" in resp.headers["Content-Disposition"]
    text = resp.get_data(as_text=True)
    lines = text.splitlines()
    assert lines[0] == "timestamp,actor,method,path,status_code,duration_ms,ip_address,category,summary"
    # The comma-and-quote-bearing summary must be CSV-quoted, not split.
    assert '"Created skill ""X, the great"""' in text
    assert "dana" in text


def test_export_csv_requires_panel_auth():
    app = _panel_app()
    c = app.test_client()
    assert c.get("/api/activity/export.csv").status_code == 401


def test_clear_empties_log_but_records_itself():
    app, c = _authed_panel()
    _seed_rows(app, [
        {"actor": "a", "method": "GET", "path": f"/api/x/{i}", "status_code": 200}
        for i in range(4)
    ])
    resp = c.post("/api/activity/clear")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "cleared"
    with app.app_context():
        rows = ActivityLog.query.all()
        # Only the clear action itself remains.
        assert len(rows) == 1
        assert rows[0].category == "admin"
        assert "Cleared activity log" in rows[0].summary


def test_retention_cap_trims_oldest():
    app = _panel_app(ACTIVITY_LOG_MAX_ROWS=3)
    c = app.test_client()
    c.post("/api/activity/login", json={"username": "owner", "password": "s3cret"})
    # Each authed request logs a row; after several, the table is capped at 3.
    for _ in range(6):
        c.get("/api/activity/session")
    with app.app_context():
        assert ActivityLog.query.count() <= 3
