"""Skills blueprint: CRUD with RBAC filtering and automatic versioning."""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from models import AuditLog, SkillVersion
from services import (
    create_skill,
    delete_skill,
    get_permission_level,
    get_visible_skill_or_404,
    require_edit,
    restore_version,
    update_skill,
    visible_skills,
)

skills_bp = Blueprint("skills", __name__, url_prefix="/api/skills")


@skills_bp.get("")
@login_required
def list_skills():
    q = (request.args.get("q") or "").strip().lower()
    tag = (request.args.get("tag") or "").strip()
    category = (request.args.get("category") or "").strip()
    owner = (request.args.get("owner") or "").strip()
    status = (request.args.get("status") or "").strip()

    result = []
    for skill in visible_skills(current_user):
        if q and q not in skill.name.lower() and q not in (skill.description or "").lower():
            continue
        if tag and tag not in (skill.tags or []):
            continue
        if category and skill.category != category:
            continue
        if status and skill.status != status:
            continue
        if owner and str(skill.owner_id) != owner and skill.owner.display_name != owner:
            continue
        result.append(
            skill.to_dict(my_permission=get_permission_level(current_user, skill))
        )
    result.sort(key=lambda s: s["updated_at"], reverse=True)
    return jsonify(result)


@skills_bp.post("")
@login_required
def create():
    skill = create_skill(current_user, request.get_json(silent=True) or {})
    return jsonify(skill.to_dict(my_permission="edit")), 201


@skills_bp.get("/<int:skill_id>")
@login_required
def get_skill(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    return jsonify(
        skill.to_dict(my_permission=get_permission_level(current_user, skill))
    )


@skills_bp.put("/<int:skill_id>")
@login_required
def update(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    require_edit(current_user, skill)
    update_skill(current_user, skill, request.get_json(silent=True) or {})
    return jsonify(
        skill.to_dict(my_permission=get_permission_level(current_user, skill))
    )


@skills_bp.delete("/<int:skill_id>")
@login_required
def delete(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    delete_skill(current_user, skill)
    return jsonify({"status": "deleted"})


@skills_bp.get("/<int:skill_id>/versions")
@login_required
def list_versions(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    versions = skill.versions.order_by(SkillVersion.version_number.desc()).all()
    return jsonify([v.to_dict(include_content=False) for v in versions])


@skills_bp.get("/<int:skill_id>/versions/<int:version_number>")
@login_required
def get_version(skill_id, version_number):
    skill = get_visible_skill_or_404(current_user, skill_id)
    version = skill.versions.filter_by(version_number=version_number).first()
    if version is None:
        return jsonify({"error": "Version not found"}), 404
    return jsonify(version.to_dict())


@skills_bp.post("/<int:skill_id>/versions/<int:version_number>/restore")
@login_required
def restore(skill_id, version_number):
    skill = get_visible_skill_or_404(current_user, skill_id)
    require_edit(current_user, skill)
    version = restore_version(current_user, skill, version_number)
    return jsonify(version.to_dict())


@skills_bp.get("/<int:skill_id>/audit")
@login_required
def audit(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    entries = skill.audit_entries.order_by(
        AuditLog.created_at.desc(), AuditLog.id.desc()
    ).all()
    return jsonify([e.to_dict() for e in entries])
