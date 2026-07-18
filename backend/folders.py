"""Folders blueprint: one global, admin-managed folder tree.

Reading the tree is open to any logged-in user (read-only navigation);
every mutation requires admin.
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from services import (
    create_folder,
    delete_folder,
    get_folder_or_404,
    require_admin,
    update_folder,
    visible_folder_tree,
)

folders_bp = Blueprint("folders", __name__, url_prefix="/api/folders")


@folders_bp.get("")
@login_required
def list_folders():
    return jsonify(visible_folder_tree(current_user))


@folders_bp.post("")
@login_required
def create():
    require_admin(current_user)
    data = request.get_json(silent=True) or {}
    folder = create_folder(current_user, data.get("name"), data.get("parent_id"))
    return jsonify(folder.to_dict(skill_count=0)), 201


@folders_bp.put("/<int:folder_id>")
@login_required
def update(folder_id):
    require_admin(current_user)
    folder = get_folder_or_404(folder_id)
    data = request.get_json(silent=True) or {}
    kwargs = {}
    if "name" in data:
        kwargs["name"] = data["name"]
    if "parent_id" in data:
        kwargs["parent_id"] = data["parent_id"]
    update_folder(current_user, folder, **kwargs)
    return jsonify(folder.to_dict())


@folders_bp.delete("/<int:folder_id>")
@login_required
def delete(folder_id):
    require_admin(current_user)
    folder = get_folder_or_404(folder_id)
    delete_folder(current_user, folder)
    return jsonify({"status": "deleted"})
