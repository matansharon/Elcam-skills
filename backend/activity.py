"""Standalone activity-admin panel, gated by credentials in backend/.env.

This gate is deliberately independent of Flask-Login: a DB admin gets no
automatic access, and the panel admin needs no DB user.
"""
import csv
import hmac
import io
from datetime import datetime
from functools import wraps

from flask import Blueprint, Response, abort, current_app, jsonify, request, session, stream_with_context

from activity_log import set_activity_summary
from models import ActivityLog, db

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


@activity_bp.post("/clear")
@activity_required
def clear():
    deleted = ActivityLog.query.delete()
    db.session.commit()
    set_activity_summary(f"Cleared activity log ({deleted} rows)", "admin")
    return jsonify({"status": "cleared", "deleted": deleted})
