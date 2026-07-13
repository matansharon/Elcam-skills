# Activity Admin Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone, `.env`-gated admin page that records every backend API operation (raw view) plus human-readable summaries of meaningful events (readable view), browsable with filters, stats, auto-refresh, and CSV export.

**Architecture:** A single `ActivityLog` table is populated by one global Flask `after_request` hook that logs every `/api/*` request. Handlers stash an optional readable summary on `flask.g` (via the already-centralized `log_action` plus a few auth calls) which the hook folds into the same row. A separate blueprint gated by a `session['activity_admin']` flag (set from credentials in `backend/.env`, independent of Flask-Login) serves login/logout and the query/stats/export/clear endpoints. The frontend adds a `/activity` route outside the main app shell with its own login screen and panel.

**Tech Stack:** Flask 3 + Flask-SQLAlchemy + Flask-Login (backend, SQLite), React 18 + React Router 6 + Vite (frontend). pytest for backend tests. No frontend test runner exists — frontend tasks are verified by `npm run build` plus explicit manual smoke steps.

## Global Constraints

- Python interpreter: `python` (the machine's `python3` is a broken Windows Store alias). Backend commands run from `backend/` with the repo venv: `C:\Users\Matan\python\Elcam-Skills\.venv\Scripts\python.exe`.
- Backend tests live in `backend/tests/`, run with `python -m pytest` from `backend/`. `conftest.py` adds `backend/` to `sys.path`, so imports are top-level (`from app import create_app`, `from models import ...`).
- Test app is built with `create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})`; pass extra config via the same `config_overrides` dict.
- The database is SQLite; SQLite-specific SQL (e.g. `strftime`) is acceptable and consistent with existing code (`_migrate_schema` uses `PRAGMA`).
- The raw log stores `request.path` (no query string) and never request bodies — do not add body logging.
- Commit messages: conventional-commit style, **no AI attribution / no `Co-Authored-By` line** (repo convention; there is a clean-commits skill enforcing this).
- Frontend dev: `cd frontend && npm run dev` (port 5173, proxies `/api` → `http://localhost:5100`); backend dev: run `backend/app.py` (port 5100). `run_dev.bat` starts both.
- Reuse existing CSS primitives from `frontend/src/styles.css` (`card`, `panel`, `data`, `badge`, `banner`, `btn`, `field`, `field-row`, `login-screen`, `login-card`, `page-header`, `subtitle`).

---

## File Structure

**Backend (new):**
- `backend/activity_log.py` — capture helpers: request timer, `record_request` (the `after_request` body), actor resolution, `set_activity_summary`, retention trim.
- `backend/activity.py` — the `activity_bp` blueprint: `@activity_required`, `check_panel_credentials`, login/logout/session, logs/stats/export/clear.
- `backend/tests/test_activity.py` — all backend tests for this feature.

**Backend (modified):**
- `backend/config.py` — `ADMIN_PANEL_USER`, `ADMIN_PANEL_PASSWORD`, `ACTIVITY_LOG_MAX_ROWS`.
- `backend/models.py` — `ActivityLog` model.
- `backend/app.py` — register hooks + blueprint.
- `backend/services.py` — `log_action` also sets the activity summary/category.
- `backend/auth.py` — set summaries for login success/failure and logout.
- `backend/.env.example` — document the new vars.

**Frontend (new):**
- `frontend/src/activity/activityApi.js` — decoupled fetch helper (no global 401 handler).
- `frontend/src/activity/ActivityPage.jsx` — session gate (login vs panel).
- `frontend/src/activity/ActivityLogin.jsx` — the `.env` login screen.
- `frontend/src/activity/ActivityPanel.jsx` — filters, table, toggle, pagination, actions.
- `frontend/src/activity/ActivityStats.jsx` — stat cards + inline SVG chart.

**Frontend (modified):**
- `frontend/src/App.jsx` — add the `/activity` route outside `Layout`.
- `frontend/src/styles.css` — a few activity-specific styles.

---

## Task 1: Config — panel credentials + retention cap

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_activity.py`

**Interfaces:**
- Produces: `Config.ADMIN_PANEL_USER` (str|None), `Config.ADMIN_PANEL_PASSWORD` (str|None), `Config.ACTIVITY_LOG_MAX_ROWS` (int|None).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_activity.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_activity.py -v` (from `backend/`)
Expected: FAIL — `KeyError: 'ADMIN_PANEL_USER'` (config keys don't exist yet).

- [ ] **Step 3: Add the config keys**

In `backend/config.py`, inside `class Config`, after the `ANALYSIS_MODEL` line add:

```python
    # Standalone activity-admin panel gate. When either is unset the panel
    # is disabled (login always fails). Independent of the DB user table.
    ADMIN_PANEL_USER = os.environ.get("ADMIN_PANEL_USER")
    ADMIN_PANEL_PASSWORD = os.environ.get("ADMIN_PANEL_PASSWORD")

    # Optional cap on stored activity rows; oldest are trimmed past it.
    # Unset/blank means keep everything.
    ACTIVITY_LOG_MAX_ROWS = (
        int(os.environ["ACTIVITY_LOG_MAX_ROWS"])
        if os.environ.get("ACTIVITY_LOG_MAX_ROWS")
        else None
    )
```

- [ ] **Step 4: Document the vars in `.env.example`**

Append to `backend/.env.example`:

```
# Activity admin panel (page at /activity). Both required to enable the panel.
ADMIN_PANEL_USER=
ADMIN_PANEL_PASSWORD=
# Optional: cap stored activity rows (oldest trimmed). Blank = keep all.
ACTIVITY_LOG_MAX_ROWS=
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_activity.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/config.py backend/.env.example backend/tests/test_activity.py
git commit -m "feat: config for activity-admin panel credentials and retention cap"
```

---

## Task 2: `ActivityLog` model

**Files:**
- Modify: `backend/models.py`
- Test: `backend/tests/test_activity.py`

**Interfaces:**
- Produces: `ActivityLog` model with columns `id, timestamp, user_id, actor, method, path, status_code, duration_ms, ip_address, summary, category` and `to_dict()` returning all of them (timestamp ISO-formatted). Table name `activity_log`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_activity.py`:

```python
from models import ActivityLog, db


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_activity.py::test_activitylog_to_dict_shape -v`
Expected: FAIL — `ImportError: cannot import name 'ActivityLog'`.

- [ ] **Step 3: Add the model**

Append to `backend/models.py` (after the `AuditLog` class):

```python
class ActivityLog(db.Model):
    """Global, app-wide activity log: one row per API request.

    Distinct from AuditLog (which is per-skill). `actor` is denormalized
    because failed logins have no user and the .env panel admin is not a
    DB row.
    """
    __tablename__ = "activity_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    actor = db.Column(db.String(120), nullable=False, default="anonymous")
    method = db.Column(db.String(10), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)
    duration_ms = db.Column(db.Integer, nullable=False, default=0)
    ip_address = db.Column(db.String(45), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(20), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "actor": self.actor,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "ip_address": self.ip_address,
            "summary": self.summary,
            "category": self.category,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_activity.py::test_activitylog_to_dict_shape -v`
Expected: PASS. `db.create_all()` in `create_app` creates the new table automatically.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/tests/test_activity.py
git commit -m "feat: add ActivityLog model for global activity logging"
```

---

## Task 3: Capture hook — log every `/api/*` request

**Files:**
- Create: `backend/activity_log.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_activity.py`

**Interfaces:**
- Produces: `activity_log.start_timer()` (before_request handler), `activity_log.record_request(response)` (after_request handler, returns the response), `activity_log.set_activity_summary(summary, category=None)` (first-wins per request; no-op outside a request context), `activity_log.trim_activity_log()` (defined here, does nothing until Task 9 wires the cap — see below).
- Consumes: `ActivityLog`, `db` from `models`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_activity.py`:

```python
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
```

Note: `conftest.py`'s `regular_user` has username `dana` and `display_name` `Dana` (from `username.capitalize()`).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_activity.py::test_request_is_logged_with_raw_fields -v`
Expected: FAIL — no rows logged (assert `len(rows) == 1` fails; hook not wired).

- [ ] **Step 3: Create the capture module**

Create `backend/activity_log.py`:

```python
"""Global request capture for the activity log.

One after_request hook writes exactly one ActivityLog row per /api/* call.
Handlers may stash a readable summary on flask.g (via set_activity_summary)
which is folded into the same row.
"""
import time

from flask import current_app, g, has_request_context, request, session
from flask_login import current_user

from models import ActivityLog, db


def set_activity_summary(summary, category=None):
    """Attach a readable summary/category to the current request's log row.

    First-wins: the primary action stays the request headline even if later
    helpers (e.g. relationship links) also log. No-op outside a request.
    """
    if not has_request_context():
        return
    if getattr(g, "activity_summary", None):
        return
    g.activity_summary = summary
    g.activity_category = category


def start_timer():
    g._activity_start = time.monotonic()


def _resolve_actor():
    try:
        if current_user.is_authenticated:
            return current_user.id, current_user.display_name
    except Exception:
        pass
    if session.get("activity_admin"):
        return None, "owner"
    return None, "anonymous"


def trim_activity_log():
    """Trim oldest rows past ACTIVITY_LOG_MAX_ROWS. No-op when unset.

    Wired to actually trim in Task 9; safe to call now.
    """
    cap = current_app.config.get("ACTIVITY_LOG_MAX_ROWS")
    if not cap:
        return
    total = db.session.query(ActivityLog.id).count()
    if total <= cap:
        return
    overflow = total - cap
    old_ids = [
        r.id
        for r in db.session.query(ActivityLog.id)
        .order_by(ActivityLog.timestamp.asc(), ActivityLog.id.asc())
        .limit(overflow)
    ]
    db.session.query(ActivityLog).filter(
        ActivityLog.id.in_(old_ids)
    ).delete(synchronize_session=False)
    db.session.commit()


def record_request(response):
    """after_request hook: log the request. Best-effort; never breaks the
    response."""
    if not request.path.startswith("/api/"):
        return response
    start = getattr(g, "_activity_start", None)
    duration_ms = int((time.monotonic() - start) * 1000) if start is not None else 0
    user_id, actor = _resolve_actor()
    try:
        db.session.add(ActivityLog(
            user_id=user_id,
            actor=actor,
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            ip_address=request.remote_addr,
            summary=getattr(g, "activity_summary", None),
            category=getattr(g, "activity_category", None),
        ))
        db.session.commit()
        trim_activity_log()
    except Exception:
        db.session.rollback()
    return response
```

- [ ] **Step 4: Wire the hooks in `app.py`**

In `backend/app.py`, inside `create_app`, after the blueprints are registered (after the `app.register_blueprint(users_bp)` line) add:

```python
    from activity_log import record_request, start_timer
    app.before_request(start_timer)
    app.after_request(record_request)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_activity.py -v`
Expected: PASS (config, model, and all three capture tests).

- [ ] **Step 6: Run the full suite (regression)**

Run: `python -m pytest -q` (from `backend/`)
Expected: all existing tests still pass (the hook only adds rows; it must not change any response).

- [ ] **Step 7: Commit**

```bash
git add backend/activity_log.py backend/app.py backend/tests/test_activity.py
git commit -m "feat: log every API request to the activity log"
```

---

## Task 4: Readable summaries for write + auth events

**Files:**
- Modify: `backend/services.py`
- Modify: `backend/auth.py`
- Test: `backend/tests/test_activity.py`

**Interfaces:**
- Consumes: `activity_log.set_activity_summary`.
- Produces: after a skill create/update, the request's ActivityLog row has `summary` set and `category="skill"`; permission changes → `category="permission"`; relationship changes → `category="relationship"`; auth events → `category="auth"`. The existing per-skill `AuditLog` rows are unchanged (regression).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_activity.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_activity.py::test_skill_create_sets_readable_summary tests/test_activity.py::test_failed_login_is_logged_readably -v`
Expected: FAIL — `summary` is `None` (nothing sets it yet).

- [ ] **Step 3: Make `log_action` set the summary**

In `backend/services.py`, replace the `log_action` function (currently lines ~23-26) with:

```python
def _category_for(action):
    if action.startswith("permission"):
        return "permission"
    if action.startswith("relationship"):
        return "relationship"
    return "skill"


def log_action(skill_id, user_id, action, detail=""):
    db.session.add(
        AuditLog(skill_id=skill_id, user_id=user_id, action=action, detail=detail)
    )
    set_activity_summary(detail, _category_for(action))
```

Add the import near the top of `backend/services.py` (after the `from models import (...)` block):

```python
from activity_log import set_activity_summary
```

- [ ] **Step 4: Set auth summaries in `auth.py`**

In `backend/auth.py`, add the import after the existing imports:

```python
from activity_log import set_activity_summary
```

In `login()`, on the failure branch, set a summary before returning. Replace:

```python
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "Invalid username or password"}), 401

    login_user(user)
    return jsonify(user.to_dict())
```

with:

```python
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        set_activity_summary(f"Failed login for '{username}'", "auth")
        return jsonify({"error": "Invalid username or password"}), 401

    login_user(user)
    set_activity_summary("Signed in", "auth")
    return jsonify(user.to_dict())
```

In `logout()`, set a summary. Replace:

```python
    logout_user()
    return jsonify({"status": "ok"})
```

with:

```python
    set_activity_summary("Signed out", "auth")
    logout_user()
    return jsonify({"status": "ok"})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_activity.py -v`
Expected: PASS (including the two new summary tests and the regression assertion).

- [ ] **Step 6: Full suite regression**

Run: `python -m pytest -q`
Expected: all pass. (Watch for import cycles: `services` and `auth` now import `activity_log`, which imports `models` only — no cycle.)

- [ ] **Step 7: Commit**

```bash
git add backend/services.py backend/auth.py backend/tests/test_activity.py
git commit -m "feat: readable summaries for skill and auth events in activity log"
```

---

## Task 5: `.env` gate — blueprint login/logout/session + guard

**Files:**
- Create: `backend/activity.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_activity.py`

**Interfaces:**
- Produces:
  - Blueprint `activity_bp` at `/api/activity`.
  - `POST /api/activity/login` — `{username, password}` → 200 `{authenticated: true}` on match, 401 otherwise; sets `session['activity_admin']`.
  - `POST /api/activity/logout` → 200 `{authenticated: false}`; clears the flag.
  - `GET /api/activity/session` → `{authenticated: bool}` (no guard).
  - `@activity_required` decorator → 401 `{error: ...}` unless `session['activity_admin']`.
  - `check_panel_credentials(username, password)` → bool (constant-time; False when creds unset).
- Consumes: `activity_log.set_activity_summary`; `Config.ADMIN_PANEL_USER/PASSWORD`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_activity.py`:

```python
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
```

Note: the `@activity_required` guard is exercised end-to-end in Task 6 (via
`test_logs_endpoint_requires_panel_auth`), once a guarded route exists. Do
not add a guard test here — there is no guarded route yet.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_activity.py::test_panel_login_success_and_session -v`
Expected: FAIL — 404 on `/api/activity/login` (blueprint not registered).

- [ ] **Step 3: Create the blueprint**

Create `backend/activity.py`:

```python
"""Standalone activity-admin panel, gated by credentials in backend/.env.

This gate is deliberately independent of Flask-Login: a DB admin gets no
automatic access, and the panel admin needs no DB user.
"""
import hmac
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session

from activity_log import set_activity_summary

activity_bp = Blueprint("activity", __name__, url_prefix="/api/activity")


def check_panel_credentials(username, password):
    cfg_user = current_app.config.get("ADMIN_PANEL_USER")
    cfg_pass = current_app.config.get("ADMIN_PANEL_PASSWORD")
    if not cfg_user or not cfg_pass:
        return False  # panel disabled until both are configured
    user_ok = hmac.compare_digest(username, cfg_user)
    pass_ok = hmac.compare_digest(password, cfg_pass)
    return user_ok and pass_ok


def activity_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("activity_admin"):
            return jsonify({"error": "Activity admin authentication required"}), 401
        return fn(*args, **kwargs)
    return wrapper


@activity_bp.post("/login")
def panel_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not check_panel_credentials(username, password):
        set_activity_summary("Failed admin-panel login", "admin")
        return jsonify({"error": "Invalid credentials"}), 401
    session["activity_admin"] = True
    set_activity_summary("Admin-panel sign-in", "admin")
    return jsonify({"authenticated": True})


@activity_bp.post("/logout")
def panel_logout():
    session.pop("activity_admin", None)
    set_activity_summary("Admin-panel sign-out", "admin")
    return jsonify({"authenticated": False})


@activity_bp.get("/session")
def panel_session():
    return jsonify({"authenticated": bool(session.get("activity_admin"))})
```

- [ ] **Step 4: Register the blueprint in `app.py`**

In `backend/app.py`, add to the blueprint imports/registration block:

```python
    from activity import activity_bp
    app.register_blueprint(activity_bp)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_activity.py -v`
Expected: PASS (the skipped `/logs` test shows as skipped).

- [ ] **Step 6: Commit**

```bash
git add backend/activity.py backend/app.py backend/tests/test_activity.py
git commit -m "feat: .env-gated activity panel login/logout/session"
```

---

## Task 6: Query endpoint — `GET /api/activity/logs`

**Files:**
- Modify: `backend/activity.py`
- Test: `backend/tests/test_activity.py`

**Interfaces:**
- Consumes: `activity_required`; `ActivityLog`, `db`.
- Produces: `GET /api/activity/logs` → `{items: [ActivityLog.to_dict()], page, page_size, total}`. Query params: `page` (≥1, default 1), `page_size` (1..200, default 50), `actor`, `category`, `method`, `status` (int), `date_from`/`date_to` (ISO 8601), `q` (substring over path+summary), `view` (`raw` default | `readable` = only rows with a summary). Ordered newest-first. Invalid `status`/`page`/`page_size`/dates → 400.
- Produces helpers used by later tasks: `_base_filtered_query()` (returns a filtered `ActivityLog` query honoring all filters except pagination), `_pagination()` → `(page, page_size)`.

- [ ] **Step 1: Write the guard + filter tests**

In `backend/tests/test_activity.py`, add:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_activity.py::test_logs_pagination_and_total -v`
Expected: FAIL — 404 (no `/logs` route yet).

- [ ] **Step 3: Implement the query helpers and route**

Add to `backend/activity.py`. First extend the imports:

```python
from datetime import datetime

from flask import abort

from models import ActivityLog, db
```

Then add:

```python
def _parse_dt(value, field):
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        abort(400, description=f"Invalid {field} (use ISO 8601)")


def _pagination():
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        abort(400, description="page must be an integer")
    try:
        page_size = int(request.args.get("page_size", 50))
    except (TypeError, ValueError):
        abort(400, description="page_size must be an integer")
    return page, max(1, min(page_size, 200))


def _base_filtered_query():
    args = request.args
    q = ActivityLog.query

    actor = (args.get("actor") or "").strip()
    category = (args.get("category") or "").strip()
    method = (args.get("method") or "").strip().upper()
    status = (args.get("status") or "").strip()
    date_from = (args.get("date_from") or "").strip()
    date_to = (args.get("date_to") or "").strip()
    text = (args.get("q") or "").strip()
    view = (args.get("view") or "").strip()

    if actor:
        q = q.filter(ActivityLog.actor == actor)
    if category:
        q = q.filter(ActivityLog.category == category)
    if method:
        q = q.filter(ActivityLog.method == method)
    if status:
        if not status.isdigit():
            abort(400, description="status must be an integer")
        q = q.filter(ActivityLog.status_code == int(status))
    if date_from:
        q = q.filter(ActivityLog.timestamp >= _parse_dt(date_from, "date_from"))
    if date_to:
        q = q.filter(ActivityLog.timestamp <= _parse_dt(date_to, "date_to"))
    if text:
        like = f"%{text}%"
        q = q.filter(db.or_(ActivityLog.path.ilike(like), ActivityLog.summary.ilike(like)))
    if view == "readable":
        q = q.filter(ActivityLog.summary.isnot(None))
    return q


@activity_bp.get("/logs")
@activity_required
def logs():
    page, page_size = _pagination()
    q = _base_filtered_query()
    total = q.count()
    items = (
        q.order_by(ActivityLog.timestamp.desc(), ActivityLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return jsonify({
        "items": [a.to_dict() for a in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_activity.py -v`
Expected: PASS (all logs tests + the previously skipped guard test).

- [ ] **Step 5: Commit**

```bash
git add backend/activity.py backend/tests/test_activity.py
git commit -m "feat: activity logs query endpoint with filters and pagination"
```

---

## Task 7: Stats endpoint — `GET /api/activity/stats`

**Files:**
- Modify: `backend/activity.py`
- Test: `backend/tests/test_activity.py`

**Interfaces:**
- Consumes: `_base_filtered_query`, `activity_required`.
- Produces: `GET /api/activity/stats` → `{total, active_users, by_category: [{category, count}], by_method: [{method, count}], timeline: [{bucket, count}]}` where `bucket` is a `YYYY-MM-DD` day. Honors the same filters as `/logs` (except pagination). Null categories are reported as `"request"`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_activity.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_activity.py::test_stats_shape_and_counts -v`
Expected: FAIL — 404 (no `/stats` route).

- [ ] **Step 3: Implement the stats route**

Add to `backend/activity.py`:

```python
@activity_bp.get("/stats")
@activity_required
def stats():
    q = _base_filtered_query()
    total = q.count()
    active_users = q.with_entities(ActivityLog.actor).distinct().count()

    by_category = (
        q.with_entities(ActivityLog.category, db.func.count())
        .group_by(ActivityLog.category)
        .all()
    )
    by_method = (
        q.with_entities(ActivityLog.method, db.func.count())
        .group_by(ActivityLog.method)
        .all()
    )
    day = db.func.strftime("%Y-%m-%d", ActivityLog.timestamp)
    timeline = (
        q.with_entities(day.label("bucket"), db.func.count())
        .group_by("bucket")
        .order_by("bucket")
        .all()
    )
    return jsonify({
        "total": total,
        "active_users": active_users,
        "by_category": [
            {"category": c or "request", "count": n} for c, n in by_category
        ],
        "by_method": [{"method": m, "count": n} for m, n in by_method],
        "timeline": [{"bucket": b, "count": n} for b, n in timeline],
    })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_activity.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/activity.py backend/tests/test_activity.py
git commit -m "feat: activity stats endpoint (totals, breakdowns, timeline)"
```

---

## Task 8: CSV export — `GET /api/activity/export.csv`

**Files:**
- Modify: `backend/activity.py`
- Test: `backend/tests/test_activity.py`

**Interfaces:**
- Consumes: `_base_filtered_query`, `activity_required`.
- Produces: `GET /api/activity/export.csv` → streamed `text/csv` with header row `timestamp,actor,method,path,status_code,duration_ms,ip_address,category,summary`, one row per matching log (newest-first), honoring the same filters as `/logs`. `Content-Disposition: attachment; filename=activity-log.csv`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_activity.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_activity.py::test_export_csv_contains_rows_and_escapes -v`
Expected: FAIL — 404 (no export route).

- [ ] **Step 3: Implement the export route**

Extend the imports at the top of `backend/activity.py`:

```python
import csv
import io

from flask import Response, stream_with_context
```

Add the route:

```python
_CSV_COLUMNS = [
    "timestamp", "actor", "method", "path", "status_code",
    "duration_ms", "ip_address", "category", "summary",
]


@activity_bp.get("/export.csv")
@activity_required
def export_csv():
    q = _base_filtered_query().order_by(
        ActivityLog.timestamp.desc(), ActivityLog.id.desc()
    )

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(_CSV_COLUMNS)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        for a in q:
            writer.writerow([
                a.timestamp.isoformat(), a.actor, a.method, a.path,
                a.status_code, a.duration_ms, a.ip_address or "",
                a.category or "", a.summary or "",
            ])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    headers = {"Content-Disposition": "attachment; filename=activity-log.csv"}
    return Response(stream_with_context(generate()), mimetype="text/csv", headers=headers)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_activity.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/activity.py backend/tests/test_activity.py
git commit -m "feat: CSV export of the activity log"
```

---

## Task 9: Clear endpoint + retention trim wiring

**Files:**
- Modify: `backend/activity.py`
- Test: `backend/tests/test_activity.py`

**Interfaces:**
- Consumes: `activity_required`, `set_activity_summary`; `trim_activity_log` already invoked by `record_request` (Task 3) and reads `ACTIVITY_LOG_MAX_ROWS`.
- Produces: `POST /api/activity/clear` → deletes all rows, returns `{status: "cleared", deleted: N}`; the clear action is itself logged (so exactly one row — the clear — remains afterward).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_activity.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_activity.py::test_clear_empties_log_but_records_itself -v`
Expected: FAIL — 404 (no clear route).

- [ ] **Step 3: Implement the clear route**

Add to `backend/activity.py`:

```python
@activity_bp.post("/clear")
@activity_required
def clear():
    deleted = ActivityLog.query.delete()
    db.session.commit()
    set_activity_summary(f"Cleared activity log ({deleted} rows)", "admin")
    return jsonify({"status": "cleared", "deleted": deleted})
```

Note: `trim_activity_log` is already called from `record_request` (Task 3), so the retention test needs no new backend code here — this task only adds `/clear` and verifies both behaviors.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_activity.py -v`
Expected: PASS (clear + retention).

- [ ] **Step 5: Full backend suite regression**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/activity.py backend/tests/test_activity.py
git commit -m "feat: clear activity log endpoint and retention trim"
```

---

## Task 10: Frontend — `/activity` route, API helper, session gate + login

**Files:**
- Create: `frontend/src/activity/activityApi.js`
- Create: `frontend/src/activity/ActivityPage.jsx`
- Create: `frontend/src/activity/ActivityLogin.jsx`
- Create: `frontend/src/activity/ActivityPanel.jsx` (minimal shell this task)
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: backend `/api/activity/session`, `/login`, `/logout`.
- Produces: a `/activity` page (outside the app shell, not in nav) that shows the login screen when unauthenticated and a panel shell (with a Sign-out button) when authenticated.

- [ ] **Step 1: Create the decoupled API helper**

Create `frontend/src/activity/activityApi.js`:

```javascript
// Standalone transport for the activity panel. Unlike the app's shared
// client it has no global 401 handler, so a panel 401 never disturbs the
// main app's auth state.
async function send(path, opts) {
  const resp = await fetch(path, opts)
  let data = null
  try {
    data = await resp.json()
  } catch {
    data = null
  }
  if (!resp.ok) {
    const err = new Error(data?.error || `Request failed (${resp.status})`)
    err.status = resp.status
    throw err
  }
  return data
}

function request(method, path, body) {
  const opts = { method, credentials: 'include', headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  return send(path, opts)
}

export const activityApi = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
}
```

- [ ] **Step 2: Create the session gate page**

Create `frontend/src/activity/ActivityPage.jsx`:

```jsx
import { useEffect, useState } from 'react'
import { activityApi } from './activityApi'
import ActivityLogin from './ActivityLogin'
import ActivityPanel from './ActivityPanel'

export default function ActivityPage() {
  const [authed, setAuthed] = useState(null) // null = still checking

  useEffect(() => {
    activityApi
      .get('/api/activity/session')
      .then((d) => setAuthed(!!d.authenticated))
      .catch(() => setAuthed(false))
  }, [])

  if (authed === null) return <div className="page-loading">Loading…</div>
  if (!authed) return <ActivityLogin onSuccess={() => setAuthed(true)} />
  return <ActivityPanel onLogout={() => setAuthed(false)} />
}
```

- [ ] **Step 3: Create the login screen**

Create `frontend/src/activity/ActivityLogin.jsx`:

```jsx
import { useState } from 'react'
import { activityApi } from './activityApi'

export default function ActivityLogin({ onSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await activityApi.post('/api/activity/login', { username, password })
      onSuccess()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <div className="wordmark">
          <span className="wordmark-block" />
          <span className="wordmark-text">
            ELCAM <em>/</em> ACTIVITY
          </span>
        </div>
        <h1>Admin sign in</h1>
        <p className="login-hint">Restricted: activity monitoring console.</p>
        {error && <div className="banner banner-error">{error}</div>}
        <label>
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Create the minimal panel shell**

Create `frontend/src/activity/ActivityPanel.jsx`:

```jsx
import { activityApi } from './activityApi'

export default function ActivityPanel({ onLogout }) {
  const signOut = async () => {
    try {
      await activityApi.post('/api/activity/logout')
    } catch {
      // already signed out
    }
    onLogout()
  }

  return (
    <div className="activity-shell">
      <div className="page-header">
        <div>
          <h1>Activity</h1>
          <div className="subtitle">All operations across the app.</div>
        </div>
        <button className="btn btn-ghost" onClick={signOut}>
          Sign out
        </button>
      </div>
      <div className="card panel">Panel coming online…</div>
    </div>
  )
}
```

- [ ] **Step 5: Wire the route in `App.jsx`**

In `frontend/src/App.jsx`, add the import near the other page imports:

```jsx
import ActivityPage from './activity/ActivityPage'
```

Then add the route as a top-level sibling, immediately before the `<Route path="*" ...>` catch-all:

```jsx
      <Route path="/activity" element={<ActivityPage />} />
```

- [ ] **Step 6: Build to verify (no frontend test runner)**

Run: `cd frontend && npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 7: Manual smoke**

1. Set `ADMIN_PANEL_USER=owner` and `ADMIN_PANEL_PASSWORD=s3cret` in `backend/.env`.
2. Start both: run `run_dev.bat` (backend :5100, frontend :5173).
3. Open `http://localhost:5173/activity`. Expected: the "ELCAM / ACTIVITY" login screen.
4. Enter wrong creds → error banner. Enter `owner` / `s3cret` → the "Activity" panel shell with a Sign out button.
5. Click Sign out → back to login screen.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/activity/ frontend/src/App.jsx
git commit -m "feat: activity page route with .env-gated login shell"
```

---

## Task 11: Frontend — log table with Raw/Readable toggle, filters, pagination

**Files:**
- Modify: `frontend/src/activity/ActivityPanel.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `GET /api/activity/logs` with `page, page_size, view, actor, category, method, status, q`.
- Produces: a filterable, paginated table with a Raw⇄Readable toggle. Raw view shows time/actor/method/path/status/duration; Readable view shows time/actor/category/summary.

- [ ] **Step 1: Replace the panel body with the table implementation**

Replace the entire contents of `frontend/src/activity/ActivityPanel.jsx` with:

```jsx
import { useCallback, useEffect, useState } from 'react'
import { activityApi } from './activityApi'

const EMPTY_FILTERS = { actor: '', category: '', method: '', status: '', q: '' }
const PAGE_SIZE = 50

function buildQuery({ view, page, filters }) {
  const params = new URLSearchParams({ view, page: String(page), page_size: String(PAGE_SIZE) })
  Object.entries(filters).forEach(([k, v]) => {
    if (v) params.set(k, v)
  })
  return params.toString()
}

export default function ActivityPanel({ onLogout }) {
  const [view, setView] = useState('raw')
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE })
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const q = buildQuery({ view, page, filters })
      setData(await activityApi.get(`/api/activity/logs?${q}`))
    } catch (err) {
      setError(err.message)
    }
  }, [view, page, filters])

  useEffect(() => {
    load()
  }, [load])

  const setFilter = (key) => (e) => {
    setPage(1)
    setFilters((f) => ({ ...f, [key]: e.target.value }))
  }

  const signOut = async () => {
    try {
      await activityApi.post('/api/activity/logout')
    } catch {
      /* already gone */
    }
    onLogout()
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))

  return (
    <div className="activity-shell">
      <div className="page-header">
        <div>
          <h1>Activity</h1>
          <div className="subtitle">All operations across the app.</div>
        </div>
        <button className="btn btn-ghost" onClick={signOut}>
          Sign out
        </button>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <div className="card panel">
        <div className="activity-toolbar">
          <div className="activity-toggle">
            <button
              className={`btn btn-small ${view === 'raw' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => { setView('raw'); setPage(1) }}
            >
              Raw
            </button>
            <button
              className={`btn btn-small ${view === 'readable' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => { setView('readable'); setPage(1) }}
            >
              Readable
            </button>
          </div>
          <div className="activity-filters">
            <input placeholder="Search path/summary" value={filters.q} onChange={setFilter('q')} />
            <input placeholder="Actor" value={filters.actor} onChange={setFilter('actor')} />
            <select value={filters.category} onChange={setFilter('category')}>
              <option value="">All categories</option>
              <option value="auth">auth</option>
              <option value="skill">skill</option>
              <option value="permission">permission</option>
              <option value="relationship">relationship</option>
              <option value="admin">admin</option>
            </select>
            <select value={filters.method} onChange={setFilter('method')}>
              <option value="">All methods</option>
              <option>GET</option>
              <option>POST</option>
              <option>PUT</option>
              <option>DELETE</option>
            </select>
            <input placeholder="Status" value={filters.status} onChange={setFilter('status')} />
          </div>
        </div>

        <div className="table-wrap">
          <table className="data">
            <thead>
              {view === 'raw' ? (
                <tr>
                  <th>Time</th><th>Actor</th><th>Method</th><th>Path</th><th>Status</th><th>ms</th>
                </tr>
              ) : (
                <tr>
                  <th>Time</th><th>Actor</th><th>Category</th><th>Summary</th>
                </tr>
              )}
            </thead>
            <tbody>
              {data.items.map((r) =>
                view === 'raw' ? (
                  <tr key={r.id}>
                    <td className="cell-muted">{new Date(r.timestamp).toLocaleString()}</td>
                    <td>{r.actor}</td>
                    <td><span className="badge">{r.method}</span></td>
                    <td className="mono">{r.path}</td>
                    <td>{r.status_code}</td>
                    <td className="cell-muted">{r.duration_ms}</td>
                  </tr>
                ) : (
                  <tr key={r.id}>
                    <td className="cell-muted">{new Date(r.timestamp).toLocaleString()}</td>
                    <td>{r.actor}</td>
                    <td>{r.category && <span className="badge badge-perm">{r.category}</span>}</td>
                    <td>{r.summary}</td>
                  </tr>
                )
              )}
              {data.items.length === 0 && (
                <tr><td colSpan={view === 'raw' ? 6 : 4} className="cell-muted">No activity.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="activity-pager">
          <button className="btn btn-small btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Prev
          </button>
          <span className="cell-muted">Page {data.page} of {totalPages} · {data.total} events</span>
          <button className="btn btn-small btn-ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add styles**

Append to `frontend/src/styles.css`:

```css
/* Activity admin panel */
.activity-shell { max-width: 1100px; margin: 0 auto; }
.activity-toolbar {
  display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
  justify-content: space-between; margin-bottom: 14px;
}
.activity-toggle { display: flex; gap: 6px; }
.activity-filters { display: flex; flex-wrap: wrap; gap: 8px; }
.activity-filters input, .activity-filters select { padding: 6px 8px; }
.activity-pager {
  display: flex; align-items: center; gap: 14px; justify-content: flex-end;
  margin-top: 14px;
}
```

- [ ] **Step 3: Build to verify**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Manual smoke**

1. With the app running and signed into `/activity`: in another tab, sign into the main app and create/edit a skill, then sign out and attempt one bad login.
2. Back on `/activity`: the table lists rows. Toggle **Raw** vs **Readable** — Readable shows only rows with summaries (e.g., "Created skill '…'", "Failed login for '…'").
3. Type in **Search**, set **Actor**/**Category**/**Method**/**Status** filters — the table narrows. Paging Prev/Next works.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/activity/ActivityPanel.jsx frontend/src/styles.css
git commit -m "feat: activity log table with raw/readable toggle and filters"
```

---

## Task 12: Frontend — stat cards + inline SVG timeline chart

**Files:**
- Create: `frontend/src/activity/ActivityStats.jsx`
- Modify: `frontend/src/activity/ActivityPanel.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `GET /api/activity/stats` (same filters as logs). `ActivityStats` accepts a `filters` object and a `refreshKey` (any value that changes when a reload is wanted) and fetches on change.
- Produces: a row of stat cards (Total events, Active users, top category) and a small dependency-free SVG bar chart of the `timeline`.

- [ ] **Step 1: Create the stats component**

Create `frontend/src/activity/ActivityStats.jsx`:

```jsx
import { useEffect, useState } from 'react'
import { activityApi } from './activityApi'

function statsQuery(filters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => {
    if (v) params.set(k, v)
  })
  return params.toString()
}

function TimelineChart({ timeline }) {
  if (!timeline || timeline.length === 0) return <div className="cell-muted">No data yet.</div>
  const max = Math.max(...timeline.map((t) => t.count), 1)
  const barW = 22
  const gap = 8
  const height = 90
  const width = timeline.length * (barW + gap)
  return (
    <svg className="activity-chart" viewBox={`0 0 ${width} ${height + 20}`} width="100%" height={height + 20}>
      {timeline.map((t, i) => {
        const h = Math.round((t.count / max) * height)
        const x = i * (barW + gap)
        return (
          <g key={t.bucket}>
            <rect x={x} y={height - h} width={barW} height={h} rx="3" className="activity-bar" />
            <text x={x + barW / 2} y={height + 14} textAnchor="middle" className="activity-bar-label">
              {t.bucket.slice(5)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export default function ActivityStats({ filters, refreshKey }) {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    activityApi
      .get(`/api/activity/stats?${statsQuery(filters)}`)
      .then(setStats)
      .catch(() => setStats(null))
  }, [filters, refreshKey])

  if (!stats) return null
  const topCategory = [...stats.by_category].sort((a, b) => b.count - a.count)[0]

  return (
    <div className="activity-stats">
      <div className="stat-cards">
        <div className="card stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">Total events</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{stats.active_users}</div>
          <div className="stat-label">Active actors</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{topCategory ? topCategory.category : '—'}</div>
          <div className="stat-label">Top category</div>
        </div>
      </div>
      <div className="card panel">
        <h3 style={{ fontSize: 14, marginTop: 0 }}>Activity over time</h3>
        <TimelineChart timeline={stats.timeline} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Mount it in the panel**

In `frontend/src/activity/ActivityPanel.jsx`, add the import:

```jsx
import ActivityStats from './ActivityStats'
```

Render it directly after the `{error && ...}` banner line and before the main `<div className="card panel">`:

```jsx
      <ActivityStats filters={filters} refreshKey={`${view}-${page}`} />
```

- [ ] **Step 3: Add styles**

Append to `frontend/src/styles.css`:

```css
.activity-stats { margin-bottom: 16px; }
.stat-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 12px; }
.stat-card { padding: 16px; }
.stat-value { font-size: 26px; font-weight: 700; }
.stat-label { color: var(--muted, #888); font-size: 13px; margin-top: 4px; }
.activity-chart { display: block; }
.activity-bar { fill: #4f6df5; }
.activity-bar-label { font-size: 9px; fill: var(--muted, #888); }
```

- [ ] **Step 4: Build to verify**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Manual smoke**

Reload `/activity`. Expected: three stat cards populate, and the bar chart shows one or more day bars. Changing a filter updates both the table and the cards/chart.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/activity/ActivityStats.jsx frontend/src/activity/ActivityPanel.jsx frontend/src/styles.css
git commit -m "feat: activity summary stat cards and timeline chart"
```

---

## Task 13: Frontend — auto-refresh, CSV export, clear log

**Files:**
- Modify: `frontend/src/activity/ActivityPanel.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `GET /api/activity/export.csv` (cookie-authed same-origin download), `POST /api/activity/clear`.
- Produces: an Auto-refresh toggle (polls logs + stats every 5s), an Export CSV button (downloads the current filtered set), and a Clear log button (with confirmation).

- [ ] **Step 1: Add the three controls to the panel**

In `frontend/src/activity/ActivityPanel.jsx`:

Add `useRef` to the React import:

```jsx
import { useCallback, useEffect, useRef, useState } from 'react'
```

Add auto-refresh state near the other `useState` calls:

```jsx
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshTick, setRefreshTick] = useState(0)
  const timerRef = useRef(null)
```

Add a polling effect after the existing `useEffect(() => { load() }, [load])`:

```jsx
  useEffect(() => {
    if (!autoRefresh) return undefined
    timerRef.current = setInterval(() => {
      load()
      setRefreshTick((t) => t + 1)
    }, 5000)
    return () => clearInterval(timerRef.current)
  }, [autoRefresh, load])
```

Add the export and clear handlers after `signOut`:

```jsx
  const exportCsv = () => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.set(k, v)
    })
    const qs = params.toString()
    const a = document.createElement('a')
    a.href = `/api/activity/export.csv${qs ? `?${qs}` : ''}`
    a.download = 'activity-log.csv'
    document.body.appendChild(a)
    a.click()
    a.remove()
  }

  const clearLog = async () => {
    if (!window.confirm('Permanently delete all recorded activity? This cannot be undone.')) return
    setError(null)
    try {
      await activityApi.post('/api/activity/clear')
      setPage(1)
      await load()
      setRefreshTick((t) => t + 1)
    } catch (err) {
      setError(err.message)
    }
  }
```

Update the `ActivityStats` mount to also depend on the tick so it refreshes together:

```jsx
      <ActivityStats filters={filters} refreshKey={`${view}-${page}-${refreshTick}`} />
```

Add the buttons to the toolbar — inside `.activity-toggle`, after the Readable button, add a right-side action group. Replace the `.activity-toolbar` opening block's `.activity-toggle` div with this expanded version:

```jsx
          <div className="activity-toggle">
            <button
              className={`btn btn-small ${view === 'raw' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => { setView('raw'); setPage(1) }}
            >
              Raw
            </button>
            <button
              className={`btn btn-small ${view === 'readable' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => { setView('readable'); setPage(1) }}
            >
              Readable
            </button>
            <label className="activity-auto">
              <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
              Auto-refresh
            </label>
            <button className="btn btn-small btn-ghost" onClick={exportCsv}>Export CSV</button>
            <button className="btn btn-small btn-danger" onClick={clearLog}>Clear log</button>
          </div>
```

- [ ] **Step 2: Add styles**

Append to `frontend/src/styles.css`:

```css
.activity-auto { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
```

- [ ] **Step 3: Build to verify**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Manual smoke**

1. On `/activity`, click **Export CSV** → a `activity-log.csv` downloads; open it and confirm the header row and current rows (respecting any active filters).
2. Toggle **Auto-refresh** on; in another tab perform an app action; within ~5s the table and cards update without a manual reload. Toggle it off.
3. Click **Clear log**, confirm the dialog → the table empties except for the single "Cleared activity log (N rows)" entry (visible in Readable view).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/activity/ActivityPanel.jsx frontend/src/styles.css
git commit -m "feat: activity panel auto-refresh, CSV export, and clear log"
```

---

## Task 14: Docs + full verification pass

**Files:**
- Modify: `README.md`
- Modify: `backend/.env.example` (verify)

**Interfaces:** none (documentation + verification).

- [ ] **Step 1: Document the panel in the README**

Add a section to `README.md` (near the existing feature/setup docs) describing the activity panel:

```markdown
## Activity admin panel

A standalone console at `/activity` records every API operation (raw view)
plus readable summaries of meaningful events (readable view). It is gated by a
credential kept in `backend/.env`, independent of the app's user accounts:

```
ADMIN_PANEL_USER=owner
ADMIN_PANEL_PASSWORD=choose-a-strong-password
# optional: cap stored rows (oldest trimmed); blank keeps everything
ACTIVITY_LOG_MAX_ROWS=
```

With both set, open `/activity`, sign in with those credentials, and browse,
filter, search, export (CSV), or clear the log. When the vars are unset the
panel is disabled (login always fails). The page is not linked from the main
navigation and its login is separate from the regular user login.
```

- [ ] **Step 2: Run the full backend suite**

Run: `python -m pytest -q` (from `backend/`)
Expected: all tests pass, including `tests/test_activity.py`.

- [ ] **Step 3: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 4: End-to-end manual verification**

With `run_dev.bat` running and `ADMIN_PANEL_*` set in `backend/.env`:
1. Perform a spread of app actions as different users (login, create/edit/delete skill, permission change, failed login, package download, AI suggest if configured).
2. On `/activity`: confirm each appears; Readable view shows friendly summaries; Raw view shows the underlying requests; failed login has no user but a readable summary; the panel admin's own requests show actor `owner`.
3. Confirm filters, search, pagination, stats, chart, auto-refresh, CSV export, and clear all behave.
4. Unset the `ADMIN_PANEL_*` vars, restart the backend, and confirm `/activity` login now fails (panel disabled).

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document the activity admin panel"
```

---

## Self-Review

**Spec coverage:**
- `.env` gate (separate creds, constant-time, disabled when unset) → Tasks 1, 5. ✅
- `session['activity_admin']` flag independent of Flask-Login → Task 5. ✅
- `ActivityLog` model with denormalized `actor` → Task 2. ✅
- Capture every `/api/*` request via `after_request`; actor resolution; best-effort; no bodies/query strings → Task 3. ✅
- Readable summaries via centralized `log_action` + auth events; per-skill `AuditLog` untouched → Task 4 (with regression assertion). ✅
- `logs` (filters/search/pagination/view), `stats`, `export.csv`, `clear` → Tasks 6, 7, 8, 9. ✅
- Retention: keep-all + `ACTIVITY_LOG_MAX_ROWS` trim + manual clear → Tasks 1, 3, 9. ✅
- Frontend `/activity` outside app shell, not in nav, own login → Task 10. ✅
- Raw⇄Readable toggle, filters/search, stats cards + chart, auto-refresh, CSV, clear, pagination → Tasks 11, 12, 13. ✅
- Reuse existing CSS primitives → Tasks 10–13. ✅
- Docs → Task 14. ✅

**Placeholder scan:** No TBD/TODO; every code step contains complete code; every command has an expected result. The one intentional two-step item (skip in Task 5, unskip in Task 6) is explicit. ✅

**Type/name consistency:** `set_activity_summary`, `record_request`, `start_timer`, `trim_activity_log`, `check_panel_credentials`, `activity_required`, `_base_filtered_query`, `_pagination`, `activity_bp` used consistently across tasks. Endpoint shapes (`{items,page,page_size,total}`; stats keys; CSV columns) match between backend producers and frontend consumers. `activityApi.get/post` used uniformly on the frontend. ✅
