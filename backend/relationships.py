"""Typed skill relationships and the graph endpoint.

The graph endpoint returns a generic {nodes, edges} shape so the
frontend visualization library can be swapped without backend changes.
"""
from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required

from models import RELATIONSHIP_TYPES, SkillRelationship, db
from services import (
    get_permission_level,
    get_visible_skill_or_404,
    log_action,
    require_edit,
    visible_skills,
)

relationships_bp = Blueprint("relationships", __name__, url_prefix="/api")


@relationships_bp.post("/relationships")
@login_required
def create_relationship():
    data = request.get_json(silent=True) or {}
    rel_type = data.get("type")
    if rel_type not in RELATIONSHIP_TYPES:
        abort(400, description=f"Type must be one of: {', '.join(RELATIONSHIP_TYPES)}")

    source_id = data.get("source_skill_id")
    target_id = data.get("target_skill_id")
    if source_id == target_id:
        abort(400, description="A skill cannot be linked to itself")

    source = get_visible_skill_or_404(current_user, source_id)
    target = get_visible_skill_or_404(current_user, target_id)
    require_edit(current_user, source)

    existing = SkillRelationship.query.filter_by(
        source_skill_id=source.id, target_skill_id=target.id, type=rel_type
    ).first()
    if existing:
        abort(400, description="This relationship already exists")

    rel = SkillRelationship(
        source_skill_id=source.id,
        target_skill_id=target.id,
        type=rel_type,
        created_by=current_user.id,
    )
    db.session.add(rel)
    log_action(source.id, current_user.id, "relationship_added",
               f"{source.name} {rel_type} {target.name}")
    db.session.commit()
    return jsonify(rel.to_dict()), 201


@relationships_bp.delete("/relationships/<int:rel_id>")
@login_required
def delete_relationship(rel_id):
    rel = db.session.get(SkillRelationship, rel_id)
    if rel is None:
        abort(404, description="Relationship not found")
    source = get_visible_skill_or_404(current_user, rel.source_skill_id)
    require_edit(current_user, source)

    log_action(source.id, current_user.id, "relationship_removed",
               f"{rel.source_skill.name} {rel.type} {rel.target_skill.name}")
    db.session.delete(rel)
    db.session.commit()
    return jsonify({"status": "deleted"})


@relationships_bp.get("/skills/<int:skill_id>/links")
@login_required
def skill_links(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)

    def entry(rel, other):
        return {
            "id": rel.id,
            "type": rel.type,
            "skill": {"id": other.id, "name": other.name, "status": other.status},
        }

    outgoing = [
        entry(rel, rel.target_skill)
        for rel in skill.outgoing
        if get_permission_level(current_user, rel.target_skill) is not None
    ]
    incoming = [
        entry(rel, rel.source_skill)
        for rel in skill.incoming
        if get_permission_level(current_user, rel.source_skill) is not None
    ]
    return jsonify({"outgoing": outgoing, "incoming": incoming})


@relationships_bp.get("/graph")
@login_required
def graph():
    skills = visible_skills(current_user)
    visible_ids = {s.id for s in skills}

    nodes = [
        {
            "id": s.id,
            "name": s.name,
            "category": s.category,
            "tags": s.tags or [],
            "status": s.status,
        }
        for s in skills
    ]
    edges = [
        rel.to_dict()
        for rel in SkillRelationship.query.all()
        if rel.source_skill_id in visible_ids and rel.target_skill_id in visible_ids
    ]
    return jsonify({"nodes": nodes, "edges": edges})
