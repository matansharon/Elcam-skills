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
