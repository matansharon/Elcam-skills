"""Admin-only blueprint: user management and per-skill permissions."""
from functools import wraps

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required

from models import PERMISSION_LEVELS, ROLES, Favorite, Skill, SkillPermission, User, db
from services import favorite_skill_ids, favorites_of, get_permission_level, log_action

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403, description="Admin access required")
        return fn(*args, **kwargs)
    return wrapper


@users_bp.get("")
@admin_required
def list_users():
    return jsonify([u.to_dict() for u in User.query.order_by(User.username).all()])


@users_bp.get("/<int:user_id>")
@login_required
def get_user(user_id):
    if not (current_user.is_admin or current_user.id == user_id):
        abort(404, description="User not found")
    user = db.session.get(User, user_id)
    if user is None:
        abort(404, description="User not found")
    data = user.to_dict()
    data["owned_count"] = Skill.query.filter_by(owner_id=user_id).count()
    data["favorite_count"] = Favorite.query.filter_by(user_id=user_id).count()
    return jsonify(data)


@users_bp.get("/<int:user_id>/favorites")
@login_required
def user_favorites(user_id):
    if not (current_user.is_admin or current_user.id == user_id):
        abort(404, description="User not found")
    target = db.session.get(User, user_id)
    if target is None:
        abort(404, description="User not found")
    fav_ids = favorite_skill_ids(current_user)
    skills = favorites_of(target, current_user)
    skills.sort(key=lambda s: s.updated_at, reverse=True)
    return jsonify([
        s.to_dict(
            my_permission=get_permission_level(current_user, s),
            favorited=s.id in fav_ids,
        )
        for s in skills
    ])


@users_bp.post("")
@admin_required
def create_user():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip() or username
    role = data.get("role", "user")

    if not username or not password:
        abort(400, description="Username and password are required")
    if role not in ROLES:
        abort(400, description=f"Role must be one of: {', '.join(ROLES)}")
    if User.query.filter_by(username=username).first():
        abort(400, description="Username already exists")

    user = User(username=username, display_name=display_name, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@users_bp.delete("/<int:user_id>")
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        abort(400, description="You cannot delete your own account")
    user = db.session.get(User, user_id)
    if user is None:
        abort(404, description="User not found")

    # Reassign owned skills to the acting admin so nothing is orphaned.
    Skill.query.filter_by(owner_id=user.id).update({"owner_id": current_user.id})
    SkillPermission.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    return jsonify({"status": "deleted"})


@users_bp.get("/<int:user_id>/permissions")
@admin_required
def list_permissions(user_id):
    if db.session.get(User, user_id) is None:
        abort(404, description="User not found")
    rows = (
        db.session.query(SkillPermission, Skill)
        .join(Skill, SkillPermission.skill_id == Skill.id)
        .filter(SkillPermission.user_id == user_id)
        .order_by(Skill.name)
        .all()
    )
    return jsonify([
        {"skill_id": skill.id, "skill_name": skill.name, "level": perm.level}
        for perm, skill in rows
    ])


@users_bp.put("/<int:user_id>/permissions/<int:skill_id>")
@admin_required
def set_permission(user_id, skill_id):
    user = db.session.get(User, user_id)
    skill = db.session.get(Skill, skill_id)
    if user is None or skill is None:
        abort(404, description="User or skill not found")

    level = (request.get_json(silent=True) or {}).get("level")
    perm = SkillPermission.query.filter_by(user_id=user_id, skill_id=skill_id).first()

    if level is None:
        if perm:
            db.session.delete(perm)
            log_action(skill_id, current_user.id, "permission_removed",
                       f"Removed access for {user.display_name}")
    elif level not in PERMISSION_LEVELS:
        abort(400, description=f"Level must be one of: {', '.join(PERMISSION_LEVELS)} or null")
    elif perm:
        perm.level = level
        log_action(skill_id, current_user.id, "permission_set",
                   f"Set {user.display_name} to {level}")
    else:
        db.session.add(SkillPermission(user_id=user_id, skill_id=skill_id, level=level))
        log_action(skill_id, current_user.id, "permission_set",
                   f"Set {user.display_name} to {level}")

    db.session.commit()
    return jsonify({"status": "ok", "level": level})
