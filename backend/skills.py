"""Skills blueprint: CRUD with RBAC filtering and automatic versioning."""
import io

from flask import Blueprint, abort, current_app, jsonify, request, send_file
from flask_login import current_user, login_required

from analysis import analyze_skill, AnalysisError
from models import AuditLog, SkillVersion
from packages import parse_package
from services import (
    create_skill,
    create_skill_from_package,
    create_version_from_package,
    delete_skill,
    get_permission_level,
    get_visible_skill_or_404,
    require_edit,
    restore_version,
    update_skill,
    visible_skills,
)


def _read_upload():
    """Pull the uploaded .skill file out of the multipart form."""
    file = request.files.get("file")
    if file is None or not file.filename:
        abort(400, description="A .skill file is required")
    return file.read(), file.filename


def _anthropic_client():
    """Construct a live Anthropic client. Imported lazily so the module loads
    (and the 'not configured' path works) even if the SDK is absent."""
    import anthropic
    return anthropic.Anthropic(api_key=current_app.config["ANTHROPIC_API_KEY"])


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


@skills_bp.post("/analyze")
@login_required
def analyze():
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    description = (data.get("description") or "").strip()
    if not content and not description:
        abort(400, description="Nothing to analyze")
    if not current_app.config.get("ANTHROPIC_API_KEY"):
        abort(503, description="AI analysis is not configured")

    candidates = [
        {"id": s.id, "name": s.name, "description": s.description, "category": s.category}
        for s in visible_skills(current_user)
    ]
    try:
        result = analyze_skill(
            _anthropic_client(),
            current_app.config["ANALYSIS_MODEL"],
            data.get("name", ""),
            description,
            content,
            candidates,
        )
    except AnalysisError:
        abort(502, description="AI analysis failed")
    except Exception:
        abort(502, description="AI analysis failed")
    return jsonify(result)


@skills_bp.post("/upload")
@login_required
def upload_create():
    file_bytes, filename = _read_upload()
    parsed = parse_package(file_bytes)
    if request.form.get("dry_run"):
        return jsonify(parsed)

    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    skill = create_skill_from_package(
        current_user, parsed, file_bytes, filename,
        category=request.form.get("category", ""),
        tags=tags,
        status=request.form.get("status", "draft"),
    )
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


@skills_bp.post("/<int:skill_id>/upload")
@login_required
def upload_version(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    require_edit(current_user, skill)
    file_bytes, filename = _read_upload()
    parsed = parse_package(file_bytes)
    version = create_version_from_package(
        current_user, skill, parsed, file_bytes, filename,
        change_note=request.form.get("change_note", ""),
    )
    return jsonify(version.to_dict())


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


@skills_bp.get("/<int:skill_id>/versions/<int:version_number>/package")
@login_required
def download_package(skill_id, version_number):
    skill = get_visible_skill_or_404(current_user, skill_id)
    version = skill.versions.filter_by(version_number=version_number).first()
    if version is None or version.package_blob is None:
        abort(404, description="No package for this version")
    return send_file(
        io.BytesIO(version.package_blob),
        mimetype="application/zip",
        as_attachment=True,
        download_name=version.package_filename or f"{skill.name}.skill",
    )


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
