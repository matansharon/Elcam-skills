"""Tests for .skill package upload, versioning, and download."""
import io
import zipfile


def make_package(name, description, body, extra_files=None, root_dir=None):
    """Build a .skill ZIP in memory. root_dir=None puts SKILL.md inside
    a '<name>/' directory (canonical layout); root_dir='' puts it at the
    archive root."""
    prefix = f"{name}/" if root_dir is None else root_dir
    skill_md = f"---\nname: {name}\ndescription: >-\n  {description}\n---\n\n{body}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{prefix}SKILL.md", skill_md)
        for path, content in (extra_files or {}).items():
            zf.writestr(f"{prefix}{path}", content)
    return buf.getvalue()


def upload(client, blob, filename="test.skill", **form):
    data = {"file": (io.BytesIO(blob), filename), **form}
    return client.post(
        "/api/skills/upload", data=data, content_type="multipart/form-data"
    )


# --- Task 1: version dict exposes package fields ----------------------------

def test_manual_version_has_no_package(client, admin_user, make_skill, login):
    skill_id = make_skill(admin_user, "Manual Skill")
    login(admin_user)
    resp = client.get(f"/api/skills/{skill_id}/versions")
    assert resp.status_code == 200
    v1 = resp.get_json()[0]
    assert v1["has_package"] is False
    assert v1["package_filename"] is None
    assert v1["bundled_files"] == []
