def _update(client, skill_id, content, note=""):
    resp = client.put(f"/api/skills/{skill_id}", json={
        "content": content, "change_note": note,
    })
    assert resp.status_code == 200
    return resp


def test_versions_listed_desc_with_snapshots(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Evolving", content="v1 content")
    login(regular_user)
    _update(client, skill_id, "v2 content", "second draft")
    _update(client, skill_id, "v3 content", "third draft")

    resp = client.get(f"/api/skills/{skill_id}/versions")
    assert resp.status_code == 200
    versions = resp.get_json()
    assert [v["version_number"] for v in versions] == [3, 2, 1]
    assert versions[0]["change_note"] == "third draft"
    assert versions[0]["created_by"] == "Dana"

    v1 = client.get(f"/api/skills/{skill_id}/versions/1").get_json()
    assert v1["content"] == "v1 content"
    v2 = client.get(f"/api/skills/{skill_id}/versions/2").get_json()
    assert v2["content"] == "v2 content"


def test_unknown_version_404(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Solo")
    login(regular_user)
    assert client.get(f"/api/skills/{skill_id}/versions/99").status_code == 404


def test_restore_creates_new_version(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Restorable", content="original",
                          description="original desc")
    login(regular_user)
    client.put(f"/api/skills/{skill_id}", json={
        "content": "changed", "description": "changed desc",
    })

    resp = client.post(f"/api/skills/{skill_id}/versions/1/restore")
    assert resp.status_code == 200
    restored = resp.get_json()
    assert restored["version_number"] == 3
    assert restored["content"] == "original"
    assert "Restored from version 1" in restored["change_note"]

    # skill current fields reflect the restored snapshot
    skill = client.get(f"/api/skills/{skill_id}").get_json()
    assert skill["description"] == "original desc"
    assert skill["current_version"] == 3

    # history intact: old versions untouched
    versions = client.get(f"/api/skills/{skill_id}/versions").get_json()
    assert [v["version_number"] for v in versions] == [3, 2, 1]
    v2 = client.get(f"/api/skills/{skill_id}/versions/2").get_json()
    assert v2["content"] == "changed"


def test_content_only_update_bumps_updated_at(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Timestamped", content="a")
    login(regular_user)
    before = client.get(f"/api/skills/{skill_id}").get_json()["updated_at"]
    _update(client, skill_id, "b")
    after = client.get(f"/api/skills/{skill_id}").get_json()["updated_at"]
    assert after > before


def test_read_user_can_view_but_not_restore(client, regular_user, second_user,
                                            login, make_skill, grant):
    skill_id = make_skill(regular_user, "Guarded")
    grant(second_user, skill_id, "read")
    login(second_user)
    assert client.get(f"/api/skills/{skill_id}/versions").status_code == 200
    assert client.post(f"/api/skills/{skill_id}/versions/1/restore").status_code == 403


def test_invisible_skill_versions_404(client, regular_user, second_user,
                                      login, make_skill):
    skill_id = make_skill(regular_user, "Hidden Versions")
    login(second_user)
    assert client.get(f"/api/skills/{skill_id}/versions").status_code == 404


def test_audit_trail_records_actions(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Audited", content="a")
    login(regular_user)
    _update(client, skill_id, "b")
    client.post(f"/api/skills/{skill_id}/versions/1/restore")

    resp = client.get(f"/api/skills/{skill_id}/audit")
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.get_json()]
    assert actions == ["restore", "update", "create"]
    assert all(e["user"] == "Dana" for e in resp.get_json())
