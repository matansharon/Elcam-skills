"""Authentication blueprint: session-based login via Flask-Login."""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user

from models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "Invalid username or password"}), 401

    login_user(user)
    return jsonify(user.to_dict())


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"status": "ok"})


@auth_bp.get("/me")
@login_required
def me():
    return jsonify(current_user.to_dict())
