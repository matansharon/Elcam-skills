import json

import pytest
from werkzeug.exceptions import HTTPException

from models import SkillRelationship, User, db
from services import attach_related, create_skill


def _rel_rows(app, source_id):
    with app.app_context():
        rows = SkillRelationship.query.filter_by(source_skill_id=source_id).all()
        return [(r.target_skill_id, r.type) for r in rows]


def test_manual_create_with_related(client, admin_user, login, make_skill, app):
    target = make_skill(admin_user, "Target Skill")
    login(admin_user)
    resp = client.post("/api/skills", json={
        "name": "New Skill",
        "description": "d",
        "content": "# c",
        "related": [{"target_skill_id": target, "type": "depends_on"}],
    })
    assert resp.status_code == 201
    new_id = resp.get_json()["id"]
    assert _rel_rows(app, new_id) == [(target, "depends_on")]


def test_manual_create_bad_type_rejected(client, admin_user, login, make_skill):
    target = make_skill(admin_user, "T2")
    login(admin_user)
    resp = client.post("/api/skills", json={
        "name": "Bad Type Skill", "description": "d", "content": "c",
        "related": [{"target_skill_id": target, "type": "nope"}],
    })
    assert resp.status_code == 400


def test_manual_create_non_dict_related_rejected(client, admin_user, login):
    login(admin_user)
    resp = client.post("/api/skills", json={
        "name": "Bad Related Shape", "description": "d", "content": "c",
        "related": ["not-an-object"],
    })
    assert resp.status_code == 400


def test_manual_create_invisible_target_rejected(
    client, admin_user, regular_user, login, make_skill
):
    hidden = make_skill(admin_user, "Hidden Skill")  # owned by admin
    login(regular_user)
    resp = client.post("/api/skills", json={
        "name": "Regular Skill", "description": "d", "content": "c",
        "related": [{"target_skill_id": hidden, "type": "used_with"}],
    })
    assert resp.status_code == 404


def test_create_without_related_makes_no_links(client, admin_user, login, app):
    login(admin_user)
    resp = client.post("/api/skills", json={
        "name": "Lonely Skill", "description": "d", "content": "c",
    })
    assert resp.status_code == 201
    assert _rel_rows(app, resp.get_json()["id"]) == []


def test_attach_related_rejects_self_link(app, admin_user, make_skill):
    sid = make_skill(admin_user, "Selfy")
    with app.app_context():
        from models import Skill
        skill = db.session.get(Skill, sid)
        user = db.session.get(User, admin_user["id"])
        with pytest.raises(HTTPException) as exc:
            attach_related(skill, user, [{"target_skill_id": sid, "type": "extends"}])
        assert exc.value.code == 400


def test_package_create_with_related(admin_user, login, client, make_skill, app):
    import io as _io
    import zipfile

    target = make_skill(admin_user, "Pkg Target")
    login(admin_user)

    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("demo/SKILL.md", "---\nname: Pkg Skill\ndescription: d\n---\nBody")
    buf.seek(0)

    resp = client.post("/api/skills/upload", data={
        "file": (buf, "demo.skill"),
        "related": json.dumps([{"target_skill_id": target, "type": "used_with"}]),
    }, content_type="multipart/form-data")
    assert resp.status_code == 201
    new_id = resp.get_json()["id"]
    assert _rel_rows(app, new_id) == [(target, "used_with")]
