def test_non_admin_forbidden_everywhere(client, regular_user, second_user,
                                        login, make_skill):
    skill_id = make_skill(regular_user, "Any Skill")
    login(regular_user)
    assert client.get("/api/users").status_code == 403
    assert client.post("/api/users", json={
        "username": "x", "password": "x", "display_name": "X"}).status_code == 403
    assert client.delete(f"/api/users/{second_user['id']}").status_code == 403
    assert client.get(f"/api/users/{second_user['id']}/permissions").status_code == 403
    assert client.put(
        f"/api/users/{second_user['id']}/permissions/{skill_id}",
        json={"level": "read"},
    ).status_code == 403


def test_admin_creates_lists_deletes_user(client, admin_user, login):
    login(admin_user)
    resp = client.post("/api/users", json={
        "username": "noa", "password": "noa123",
        "display_name": "Noa", "role": "user",
    })
    assert resp.status_code == 201
    new_id = resp.get_json()["id"]

    usernames = [u["username"] for u in client.get("/api/users").get_json()]
    assert "noa" in usernames

    # duplicate username rejected
    assert client.post("/api/users", json={
        "username": "noa", "password": "x", "display_name": "N",
    }).status_code == 400

    assert client.delete(f"/api/users/{new_id}").status_code == 200
    usernames = [u["username"] for u in client.get("/api/users").get_json()]
    assert "noa" not in usernames


def test_admin_cannot_delete_self(client, admin_user, login):
    login(admin_user)
    assert client.delete(f"/api/users/{admin_user['id']}").status_code == 400


def test_deleting_user_reassigns_owned_skills(client, admin_user, regular_user,
                                              login, make_skill):
    skill_id = make_skill(regular_user, "Orphan Candidate")
    login(admin_user)
    assert client.delete(f"/api/users/{regular_user['id']}").status_code == 200
    skill = client.get(f"/api/skills/{skill_id}").get_json()
    assert skill["owner"]["id"] == admin_user["id"]


def test_permission_upsert_changes_visibility(client, admin_user, regular_user,
                                              second_user, login, make_skill):
    skill_id = make_skill(regular_user, "Gated Skill")

    login(second_user)
    assert client.get(f"/api/skills/{skill_id}").status_code == 404

    login(admin_user)
    resp = client.put(
        f"/api/users/{second_user['id']}/permissions/{skill_id}",
        json={"level": "read"},
    )
    assert resp.status_code == 200

    login(second_user)
    assert client.get(f"/api/skills/{skill_id}").get_json()["my_permission"] == "read"

    # upgrade to edit (upsert, not duplicate)
    login(admin_user)
    client.put(f"/api/users/{second_user['id']}/permissions/{skill_id}",
               json={"level": "edit"})
    perms = client.get(f"/api/users/{second_user['id']}/permissions").get_json()
    assert perms == [{"skill_id": skill_id, "skill_name": "Gated Skill", "level": "edit"}]

    # remove with null level
    client.put(f"/api/users/{second_user['id']}/permissions/{skill_id}",
               json={"level": None})
    assert client.get(f"/api/users/{second_user['id']}/permissions").get_json() == []

    login(second_user)
    assert client.get(f"/api/skills/{skill_id}").status_code == 404


def test_invalid_level_rejected(client, admin_user, second_user, regular_user,
                                login, make_skill):
    skill_id = make_skill(regular_user, "Level Check")
    login(admin_user)
    assert client.put(
        f"/api/users/{second_user['id']}/permissions/{skill_id}",
        json={"level": "owner"},
    ).status_code == 400
