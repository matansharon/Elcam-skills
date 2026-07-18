def test_favorite_toggle_and_list(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Fav Skill")
    login(regular_user)

    assert client.get(f"/api/skills/{skill_id}").get_json()["favorited"] is False
    assert client.put(f"/api/skills/{skill_id}/favorite").get_json() == {"favorited": True}
    assert client.get(f"/api/skills/{skill_id}").get_json()["favorited"] is True

    favs = client.get("/api/favorites").get_json()
    assert [s["id"] for s in favs] == [skill_id]
    assert favs[0]["favorited"] is True

    # idempotent add
    assert client.put(f"/api/skills/{skill_id}/favorite").get_json() == {"favorited": True}
    assert len(client.get("/api/favorites").get_json()) == 1

    # remove
    assert client.delete(f"/api/skills/{skill_id}/favorite").get_json() == {"favorited": False}
    assert client.get("/api/favorites").get_json() == []


def test_cannot_favorite_invisible_skill(client, regular_user, second_user, login, make_skill):
    skill_id = make_skill(regular_user, "Private Skill")
    login(second_user)
    assert client.put(f"/api/skills/{skill_id}/favorite").status_code == 404


def test_favorites_filtered_by_visibility(client, admin_user, regular_user, second_user,
                                           login, make_skill, grant):
    skill_id = make_skill(regular_user, "Shared Then Revoked")
    grant(second_user, skill_id, "read")

    login(second_user)
    client.put(f"/api/skills/{skill_id}/favorite")
    assert len(client.get("/api/favorites").get_json()) == 1

    login(admin_user)
    client.put(f"/api/users/{second_user['id']}/permissions/{skill_id}", json={"level": None})

    login(second_user)
    assert client.get("/api/favorites").get_json() == []
