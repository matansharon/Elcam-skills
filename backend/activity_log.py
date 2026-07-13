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
