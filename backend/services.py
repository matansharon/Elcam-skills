"""Permission checks, versioning, and audit helpers.

All permission logic lives here so route handlers stay thin and the
storage layer can be swapped without touching the API surface.
"""
from flask import abort

from models import (
    RELATIONSHIP_TYPES,
    STATUSES,
    AuditLog,
    Favorite,
    Folder,
    Skill,
    SkillFolder,
    SkillPermission,
    SkillRelationship,
    SkillVersion,
    db,
    utcnow,
)
from activity_log import set_activity_summary

_UNSET = object()


# --- audit -----------------------------------------------------------------

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


def require_admin(user):
    if not user.is_admin:
        abort(403, description="Admin access required")


# --- favorites -------------------------------------------------------------

def favorite_skill_ids(user):
    return {f.skill_id for f in Favorite.query.filter_by(user_id=user.id)}


def toggle_favorite(user, skill, on):
    existing = Favorite.query.filter_by(user_id=user.id, skill_id=skill.id).first()
    if on and existing is None:
        db.session.add(Favorite(user_id=user.id, skill_id=skill.id))
    elif not on and existing is not None:
        db.session.delete(existing)
    db.session.commit()


def favorites_of(target_user, viewer):
    """Skills favorited by target_user, filtered to viewer's visibility."""
    fav_ids = {f.skill_id for f in Favorite.query.filter_by(user_id=target_user.id)}
    return [s for s in visible_skills(viewer) if s.id in fav_ids]


def visible_favorites(user):
    return favorites_of(user, user)


# --- folders -----------------------------------------------------------

def get_folder_or_404(folder_id):
    folder = db.session.get(Folder, folder_id)
    if folder is None:
        abort(404, description="Folder not found")
    return folder


def _sibling_name_taken(name, parent_id, exclude_id=None):
    q = Folder.query.filter_by(name=name, parent_id=parent_id)
    if exclude_id is not None:
        q = q.filter(Folder.id != exclude_id)
    return q.first() is not None


def _would_create_cycle(folder, new_parent_id):
    """True if making new_parent_id the parent of `folder` forms a cycle."""
    current_id = new_parent_id
    while current_id is not None:
        if current_id == folder.id:
            return True
        parent = db.session.get(Folder, current_id)
        current_id = parent.parent_id if parent else None
    return False


def create_folder(user, name, parent_id):
    name = (name or "").strip()
    if not name:
        abort(400, description="Folder name is required")
    if parent_id is not None and db.session.get(Folder, parent_id) is None:
        abort(400, description="Parent folder not found")
    if _sibling_name_taken(name, parent_id):
        abort(400, description="A folder with this name already exists here")
    folder = Folder(name=name, parent_id=parent_id, created_by=user.id)
    db.session.add(folder)
    db.session.commit()
    return folder


def update_folder(user, folder, name=_UNSET, parent_id=_UNSET):
    new_name = folder.name if name is _UNSET else (name or "").strip()
    if not new_name:
        abort(400, description="Folder name is required")
    new_parent_id = folder.parent_id if parent_id is _UNSET else parent_id
    if parent_id is not _UNSET and parent_id is not None:
        if db.session.get(Folder, parent_id) is None:
            abort(400, description="Parent folder not found")
        if _would_create_cycle(folder, parent_id):
            abort(400, description="Cannot move a folder into itself or a descendant")
    if _sibling_name_taken(new_name, new_parent_id, exclude_id=folder.id):
        abort(400, description="A folder with this name already exists here")
    folder.name = new_name
    folder.parent_id = new_parent_id
    db.session.commit()
    return folder


def delete_folder(user, folder):
    db.session.delete(folder)  # cascade removes subfolders + memberships
    db.session.commit()


def visible_folder_tree(user):
    """All folders as a flat list; skill_count counts memberships whose skill
    is visible to `user`. The frontend nests by parent_id."""
    visible_ids = {s.id for s in visible_skills(user)}
    counts = {}
    for link in SkillFolder.query.all():
        if link.skill_id in visible_ids:
            counts[link.folder_id] = counts.get(link.folder_id, 0) + 1
    folders = Folder.query.order_by(Folder.name).all()
    return [f.to_dict(skill_count=counts.get(f.id, 0)) for f in folders]


def skill_folders(skill):
    """List of {id, name} for the folders this skill belongs to."""
    result = []
    for link in SkillFolder.query.filter_by(skill_id=skill.id):
        folder = db.session.get(Folder, link.folder_id)
        if folder is not None:
            result.append({"id": folder.id, "name": folder.name})
    return result


def set_skill_folders(skill, folder_ids):
    """Replace the skill's folder memberships with exactly folder_ids."""
    ids = list(dict.fromkeys(folder_ids or []))  # de-dupe, keep order
    for fid in ids:
        if db.session.get(Folder, fid) is None:
            abort(400, description=f"Folder {fid} not found")
    SkillFolder.query.filter_by(skill_id=skill.id).delete()
    for fid in ids:
        db.session.add(SkillFolder(skill_id=skill.id, folder_id=fid))
    db.session.commit()


def bulk_assign(folder, skill_ids, mode):
    """mode 'move' sets each skill's membership to exactly [folder]; mode
    'add' adds folder to each skill's existing memberships."""
    if mode not in ("move", "add"):
        abort(400, description="mode must be 'move' or 'add'")
    for sid in skill_ids or []:
        if db.session.get(Skill, sid) is None:
            abort(404, description=f"Skill {sid} not found")
        if mode == "move":
            SkillFolder.query.filter_by(skill_id=sid).delete()
            db.session.add(SkillFolder(skill_id=sid, folder_id=folder.id))
        else:
            exists = SkillFolder.query.filter_by(
                skill_id=sid, folder_id=folder.id).first()
            if exists is None:
                db.session.add(SkillFolder(skill_id=sid, folder_id=folder.id))
    db.session.commit()


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


def attach_related(skill, user, related):
    """Create typed relationships from `skill` to each listed target.

    `related` is a list of {"target_skill_id": int, "type": str} (or None).
    No commit — the caller owns the transaction. Aborts 400 on bad type or a
    self-link, 404 on an invisible target; silently skips exact duplicates.
    """
    for entry in related or []:
        if not isinstance(entry, dict):
            abort(400, description="Each related entry must be an object")
        rel_type = entry.get("type")
        if rel_type not in RELATIONSHIP_TYPES:
            abort(400, description=f"Type must be one of: {', '.join(RELATIONSHIP_TYPES)}")
        target_id = entry.get("target_skill_id")
        if target_id == skill.id:
            abort(400, description="A skill cannot be linked to itself")
        target = get_visible_skill_or_404(user, target_id)
        exists = SkillRelationship.query.filter_by(
            source_skill_id=skill.id, target_skill_id=target.id, type=rel_type
        ).first()
        if exists:
            continue
        db.session.add(SkillRelationship(
            source_skill_id=skill.id,
            target_skill_id=target.id,
            type=rel_type,
            created_by=user.id,
        ))
        log_action(skill.id, user.id, "relationship_added",
                   f"{skill.name} {rel_type} {target.name}")


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
    attach_related(skill, user, data.get("related"))
    db.session.commit()
    return skill


def create_skill_from_package(user, parsed, file_bytes, filename,
                              category="", tags=None, status="draft",
                              related=None):
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
    attach_related(skill, user, related)
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
