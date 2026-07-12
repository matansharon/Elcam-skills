"""Permission checks, versioning, and audit helpers.

All permission logic lives here so route handlers stay thin and the
storage layer can be swapped without touching the API surface.
"""
from flask import abort

from models import (
    STATUSES,
    AuditLog,
    Skill,
    SkillPermission,
    SkillVersion,
    db,
    utcnow,
)


# --- audit -----------------------------------------------------------------

def log_action(skill_id, user_id, action, detail=""):
    db.session.add(
        AuditLog(skill_id=skill_id, user_id=user_id, action=action, detail=detail)
    )


# --- permissions -----------------------------------------------------------

def get_permission_level(user, skill):
    """Return 'edit', 'read', or None for this user on this skill."""
    if user.is_admin or skill.owner_id == user.id:
        return "edit"
    perm = SkillPermission.query.filter_by(user_id=user.id, skill_id=skill.id).first()
    return perm.level if perm else None


def visible_skills(user):
    if user.is_admin:
        return Skill.query.all()
    permitted_ids = db.session.query(SkillPermission.skill_id).filter_by(user_id=user.id)
    return Skill.query.filter(
        db.or_(Skill.owner_id == user.id, Skill.id.in_(permitted_ids))
    ).all()


def get_visible_skill_or_404(user, skill_id):
    """Invisible skills are indistinguishable from nonexistent ones."""
    skill = db.session.get(Skill, skill_id)
    if skill is None or get_permission_level(user, skill) is None:
        abort(404, description="Skill not found")
    return skill


def require_edit(user, skill):
    if get_permission_level(user, skill) != "edit":
        abort(403, description="Edit permission required")


# --- skill lifecycle -------------------------------------------------------

def _clean_tags(raw):
    if raw is None:
        return []
    if not isinstance(raw, list):
        abort(400, description="Tags must be a list of strings")
    return [str(t).strip() for t in raw if str(t).strip()]


def _validate_status(status):
    if status not in STATUSES:
        abort(400, description=f"Status must be one of: {', '.join(STATUSES)}")
    return status


def _snapshot(skill, user, content, change_note):
    """Create an immutable version from the skill's current fields."""
    version = SkillVersion(
        skill_id=skill.id,
        version_number=skill.current_version + 1,
        name=skill.name,
        description=skill.description,
        category=skill.category,
        tags=list(skill.tags or []),
        status=skill.status,
        content=content,
        change_note=change_note,
        created_by=user.id,
    )
    db.session.add(version)
    return version


def latest_version(skill):
    return (
        skill.versions.order_by(SkillVersion.version_number.desc()).first()
    )


def create_skill(user, data):
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, description="Name is required")
    if Skill.query.filter_by(name=name).first():
        abort(400, description="A skill with this name already exists")

    skill = Skill(
        name=name,
        description=data.get("description", ""),
        owner_id=user.id,
        category=(data.get("category") or "").strip(),
        tags=_clean_tags(data.get("tags")),
        status=_validate_status(data.get("status", "draft")),
    )
    db.session.add(skill)
    db.session.flush()

    _snapshot(skill, user, content=data.get("content", ""),
              change_note="Initial version")
    log_action(skill.id, user.id, "create", f"Created skill '{name}'")
    db.session.commit()
    return skill


def create_skill_from_package(user, parsed, file_bytes, filename,
                              category="", tags=None, status="draft"):
    """Create a skill from a parsed .skill package; the archive is stored
    on version 1. Name/description/content come from the package; the
    caller supplies the rest."""
    name = parsed["name"]
    if Skill.query.filter_by(name=name).first():
        abort(400, description="A skill with this name already exists")

    skill = Skill(
        name=name,
        description=parsed["description"],
        owner_id=user.id,
        category=(category or "").strip(),
        tags=_clean_tags(tags),
        status=_validate_status(status or "draft"),
    )
    db.session.add(skill)
    db.session.flush()

    version = _snapshot(skill, user, parsed["content"],
                        change_note=f"Uploaded package '{filename}'")
    version.package_blob = file_bytes
    version.package_filename = filename
    version.bundled_files = parsed["bundled_files"]
    log_action(skill.id, user.id, "create",
               f"Created skill '{name}' from package '{filename}'")
    db.session.commit()
    return skill


def update_skill(user, skill, data):
    name = (data.get("name") or skill.name).strip()
    if name != skill.name and Skill.query.filter_by(name=name).first():
        abort(400, description="A skill with this name already exists")

    skill.name = name
    if "description" in data:
        skill.description = data["description"] or ""
    if "category" in data:
        skill.category = (data["category"] or "").strip()
    if "tags" in data:
        skill.tags = _clean_tags(data["tags"])
    if "status" in data:
        skill.status = _validate_status(data["status"])

    content = data.get("content")
    if content is None:
        current = latest_version(skill)
        content = current.content if current else ""

    # Content-only saves leave the metadata columns untouched, so bump
    # the timestamp explicitly rather than relying on onupdate.
    skill.updated_at = utcnow()
    version = _snapshot(skill, user, content, data.get("change_note", ""))
    log_action(skill.id, user.id, "update",
               f"Saved version {version.version_number}")
    db.session.commit()
    return version


def create_version_from_package(user, skill, parsed, file_bytes, filename,
                                change_note=""):
    """Publish a parsed .skill package as the skill's next version.

    Content and description come from the package; name, category, tags,
    and status stay untouched (renaming remains a deliberate manual edit).
    """
    skill.description = parsed["description"]
    skill.updated_at = utcnow()

    version = _snapshot(skill, user, parsed["content"],
                        change_note or f"Uploaded package '{filename}'")
    version.package_blob = file_bytes
    version.package_filename = filename
    version.bundled_files = parsed["bundled_files"]
    log_action(skill.id, user.id, "upload",
               f"Uploaded package '{filename}' as version {version.version_number}")
    db.session.commit()
    return version


def restore_version(user, skill, version_number):
    old = SkillVersion.query.filter_by(
        skill_id=skill.id, version_number=version_number
    ).first()
    if old is None:
        abort(404, description="Version not found")

    conflict = Skill.query.filter(
        Skill.name == old.name, Skill.id != skill.id
    ).first()
    if conflict:
        abort(400, description="Cannot restore: another skill now uses this name")

    skill.name = old.name
    skill.description = old.description
    skill.category = old.category
    skill.tags = list(old.tags or [])
    skill.status = old.status
    skill.updated_at = utcnow()

    version = _snapshot(skill, user, old.content,
                        f"Restored from version {version_number}")
    log_action(skill.id, user.id, "restore",
               f"Restored version {version_number} as version {version.version_number}")
    db.session.commit()
    return version


def delete_skill(user, skill):
    if not (user.is_admin or skill.owner_id == user.id):
        abort(403, description="Only the owner or an admin can delete a skill")
    db.session.delete(skill)
    db.session.commit()
