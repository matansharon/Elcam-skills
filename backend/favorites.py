"""Favorites blueprint: per-user favorite skills (private to each user)."""
from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from services import (
    get_permission_level,
    get_visible_skill_or_404,
    toggle_favorite,
    visible_favorites,
)

favorites_bp = Blueprint("favorites", __name__, url_prefix="/api")


@favorites_bp.get("/favorites")
@login_required
def list_favorites():
    skills = visible_favorites(current_user)
    skills.sort(key=lambda s: s.updated_at, reverse=True)
    return jsonify([
        s.to_dict(my_permission=get_permission_level(current_user, s), favorited=True)
        for s in skills
    ])


@favorites_bp.put("/skills/<int:skill_id>/favorite")
@login_required
def add_favorite(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    toggle_favorite(current_user, skill, on=True)
    return jsonify({"favorited": True})


@favorites_bp.delete("/skills/<int:skill_id>/favorite")
@login_required
def remove_favorite(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    toggle_favorite(current_user, skill, on=False)
    return jsonify({"favorited": False})
