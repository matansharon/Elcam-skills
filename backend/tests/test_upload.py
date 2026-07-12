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


# --- Task 2: create a skill by uploading a package ---------------------------

def test_upload_creates_skill_from_package(client, admin_user, login):
    login(admin_user)
    blob = make_package(
        "pdf-magic", "Extracts tables from PDFs", "# PDF Magic\n\nDo the thing.",
        extra_files={"scripts/run.py": "print('hi')"},
    )
    resp = upload(client, blob, filename="pdf-magic.skill",
                  category="extraction", tags="pdf, tables", status="active")
    assert resp.status_code == 201, resp.get_json()
    skill = resp.get_json()
    assert skill["name"] == "pdf-magic"
    assert skill["description"] == "Extracts tables from PDFs"
    assert skill["category"] == "extraction"
    assert skill["tags"] == ["pdf", "tables"]
    assert skill["status"] == "active"
    assert skill["current_version"] == 1
    assert skill["my_permission"] == "edit"

    # version 1 carries the package and the parsed content
    v1 = client.get(f"/api/skills/{skill['id']}/versions/1").get_json()
    assert v1["has_package"] is True
    assert v1["package_filename"] == "pdf-magic.skill"
    assert v1["bundled_files"] == ["pdf-magic/scripts/run.py"]
    assert v1["content"].startswith("# PDF Magic")

    # audit trail mentions the package
    audit = client.get(f"/api/skills/{skill['id']}/audit").get_json()
    assert any(e["action"] == "create" and "pdf-magic.skill" in e["detail"]
               for e in audit)


def test_upload_accepts_root_level_skill_md(client, admin_user, login):
    login(admin_user)
    blob = make_package("root-skill", "At the root", "Body.", root_dir="")
    resp = upload(client, blob)
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "root-skill"


def test_upload_dry_run_parses_without_creating(client, admin_user, login):
    login(admin_user)
    blob = make_package("preview-me", "Just a preview", "# Preview",
                        extra_files={"references/notes.md": "notes"})
    resp = upload(client, blob, dry_run="1")
    assert resp.status_code == 200
    parsed = resp.get_json()
    assert parsed["name"] == "preview-me"
    assert parsed["description"] == "Just a preview"
    assert parsed["content"].startswith("# Preview")
    assert parsed["bundled_files"] == ["preview-me/references/notes.md"]

    names = [s["name"] for s in client.get("/api/skills").get_json()]
    assert "preview-me" not in names


def test_upload_requires_login(client):
    resp = upload(client, make_package("x", "d", "b"))
    assert resp.status_code == 401


def test_upload_rejects_missing_file(client, admin_user, login):
    login(admin_user)
    resp = client.post("/api/skills/upload", data={},
                       content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_rejects_non_zip(client, admin_user, login):
    login(admin_user)
    resp = upload(client, b"this is not a zip archive")
    assert resp.status_code == 400
    assert "ZIP" in resp.get_json()["error"]


def test_upload_rejects_zip_without_skill_md(client, admin_user, login):
    login(admin_user)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("stuff/readme.txt", "hello")
    resp = upload(client, buf.getvalue())
    assert resp.status_code == 400
    assert "SKILL.md" in resp.get_json()["error"]


def test_upload_rejects_skill_md_without_frontmatter(client, admin_user, login):
    login(admin_user)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("bad/SKILL.md", "# No frontmatter here")
    resp = upload(client, buf.getvalue())
    assert resp.status_code == 400
    assert "frontmatter" in resp.get_json()["error"]


def test_upload_rejects_frontmatter_without_name(client, admin_user, login):
    login(admin_user)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("bad/SKILL.md", "---\ndescription: no name\n---\nBody")
    resp = upload(client, buf.getvalue())
    assert resp.status_code == 400
    assert "name" in resp.get_json()["error"]


def test_upload_rejects_duplicate_name(client, admin_user, make_skill, login):
    make_skill(admin_user, "taken-name")
    login(admin_user)
    resp = upload(client, make_package("taken-name", "dup", "Body"))
    assert resp.status_code == 400
    assert "already exists" in resp.get_json()["error"]


def test_upload_rejects_oversized_file(client, admin_user, login):
    login(admin_user)
    resp = upload(client, b"x" * (20 * 1024 * 1024 + 1))
    assert resp.status_code == 400
    assert "large" in resp.get_json()["error"].lower()


# --- Task 3: upload a package as a new version -------------------------------

def upload_version(client, skill_id, blob, filename="update.skill", **form):
    data = {"file": (io.BytesIO(blob), filename), **form}
    return client.post(f"/api/skills/{skill_id}/upload", data=data,
                       content_type="multipart/form-data")


def test_upload_new_version_from_package(client, admin_user, make_skill, login):
    skill_id = make_skill(admin_user, "Existing Skill",
                          category="ops", tags=["a"], status="active")
    login(admin_user)
    blob = make_package("whatever-name", "New description from package",
                        "# Updated body")
    resp = upload_version(client, skill_id, blob, filename="v2.skill")
    assert resp.status_code == 200, resp.get_json()
    v2 = resp.get_json()
    assert v2["version_number"] == 2
    assert v2["has_package"] is True
    assert v2["package_filename"] == "v2.skill"
    assert v2["change_note"] == "Uploaded package 'v2.skill'"

    # content + description come from the package; identity fields do not
    skill = client.get(f"/api/skills/{skill_id}").get_json()
    assert skill["name"] == "Existing Skill"
    assert skill["description"] == "New description from package"
    assert skill["category"] == "ops"
    assert skill["tags"] == ["a"]
    assert skill["status"] == "active"
    assert skill["current_version"] == 2

    full = client.get(f"/api/skills/{skill_id}/versions/2").get_json()
    assert full["content"].startswith("# Updated body")

    audit = client.get(f"/api/skills/{skill_id}/audit").get_json()
    assert any(e["action"] == "upload" for e in audit)


def test_upload_new_version_custom_change_note(client, admin_user, make_skill, login):
    skill_id = make_skill(admin_user, "Noted Skill")
    login(admin_user)
    blob = make_package("x", "d", "b")
    resp = upload_version(client, skill_id, blob, change_note="big rework")
    assert resp.status_code == 200
    assert resp.get_json()["change_note"] == "big rework"


def test_upload_new_version_requires_edit(client, admin_user, regular_user,
                                          make_skill, grant, login):
    skill_id = make_skill(admin_user, "Read Only Skill")
    grant(regular_user, skill_id, "read")
    login(regular_user)
    resp = upload_version(client, skill_id, make_package("x", "d", "b"))
    assert resp.status_code == 403


def test_upload_new_version_invisible_skill_is_404(client, admin_user,
                                                   regular_user, make_skill, login):
    skill_id = make_skill(admin_user, "Hidden Skill")
    login(regular_user)
    resp = upload_version(client, skill_id, make_package("x", "d", "b"))
    assert resp.status_code == 404
