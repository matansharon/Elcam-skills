def test_user_page_self_access(client, regular_user, login, make_skill):
    s1 = make_skill(regular_user, "Owned One")
    login(regular_user)
    client.put(f"/api/skills/{s1}/favorite")

    me = client.get(f"/api/users/{regular_user['id']}").get_json()
    assert me["owned_count"] == 1
    assert me["favorite_count"] == 1
    assert me["display_name"] == "Dana"

    favs = client.get(f"/api/users/{regular_user['id']}/favorites").get_json()
    assert [s["id"] for s in favs] == [s1]


def test_admin_can_view_other_user_page(client, admin_user, regular_user, login, make_skill):
    make_skill(regular_user, "Dana Skill")
    login(admin_user)
    resp = client.get(f"/api/users/{regular_user['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["owned_count"] == 1


def test_non_admin_cannot_view_other_user_page(client, regular_user, second_user, login):
    login(regular_user)
    assert client.get(f"/api/users/{second_user['id']}").status_code == 404
    assert client.get(f"/api/users/{second_user['id']}/favorites").status_code == 404


def test_owned_skills_via_owner_filter(client, regular_user, login, make_skill):
    s1 = make_skill(regular_user, "Owner Filter Skill")
    login(regular_user)
    owned = [s["id"] for s in client.get(f"/api/skills?owner={regular_user['id']}").get_json()]
    assert owned == [s1]


def test_admin_nonexistent_user_404(client, admin_user, login):
    login(admin_user)
    assert client.get("/api/users/999999").status_code == 404
    assert client.get("/api/users/999999/favorites").status_code == 404


def test_favorite_count_matches_visible_favorites(client, admin_user, regular_user,
                                                  second_user, login, make_skill, grant):
    # second_user favorites a skill, then loses access; count must match the filtered list
    skill_id = make_skill(regular_user, "Count Consistency")
    grant(second_user, skill_id, "read")
    login(second_user)
    client.put(f"/api/skills/{skill_id}/favorite")
    login(admin_user)
    client.put(f"/api/users/{second_user['id']}/permissions/{skill_id}", json={"level": None})
    # admin views second_user's page: favorites list is filtered by the admin's visibility
    profile = client.get(f"/api/users/{second_user['id']}").get_json()
    favs = client.get(f"/api/users/{second_user['id']}/favorites").get_json()
    assert profile["favorite_count"] == len(favs)
