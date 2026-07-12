def test_create_skill(client, regular_user, login):
    login(regular_user)
    resp = client.post("/api/skills", json={
        "name": "PDF Extractor",
        "description": "Extracts tables from PDFs",
        "category": "data-extraction",
        "tags": ["pdf", "tables"],
        "status": "active",
        "content": "# PDF Extractor\n\nUse this to parse PDFs.",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "PDF Extractor"
    assert data["owner"]["display_name"] == "Dana"
    assert data["current_version"] == 1
    assert data["my_permission"] == "edit"
    assert data["tags"] == ["pdf", "tables"]


def test_create_requires_name(client, regular_user, login):
    login(regular_user)
    resp = client.post("/api/skills", json={"description": "no name"})
    assert resp.status_code == 400


def test_create_rejects_duplicate_name(client, regular_user, login, make_skill):
    make_skill(regular_user, "Dup Skill")
    login(regular_user)
    resp = client.post("/api/skills", json={"name": "Dup Skill"})
    assert resp.status_code == 400


def test_create_rejects_bad_status(client, regular_user, login):
    login(regular_user)
    resp = client.post("/api/skills", json={"name": "X", "status": "bogus"})
    assert resp.status_code == 400


def test_list_requires_auth(client):
    assert client.get("/api/skills").status_code == 401


def test_update_creates_new_version(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Versioned")
    login(regular_user)
    resp = client.put(f"/api/skills/{skill_id}", json={
        "description": "updated description",
        "content": "# Versioned\n\nNew content.",
        "change_note": "reworked content",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["current_version"] == 2
    assert data["description"] == "updated description"


def test_no_permission_means_404_and_hidden(client, regular_user, second_user,
                                            login, make_skill):
    skill_id = make_skill(regular_user, "Private Skill")
    login(second_user)
    assert client.get(f"/api/skills/{skill_id}").status_code == 404
    assert client.put(f"/api/skills/{skill_id}", json={"description": "x"}).status_code == 404
    names = [s["name"] for s in client.get("/api/skills").get_json()]
    assert "Private Skill" not in names


def test_read_permission_allows_get_not_put(client, regular_user, second_user,
                                            login, make_skill, grant):
    skill_id = make_skill(regular_user, "Readable Skill")
    grant(second_user, skill_id, "read")
    login(second_user)
    resp = client.get(f"/api/skills/{skill_id}")
    assert resp.status_code == 200
    assert resp.get_json()["my_permission"] == "read"
    assert client.put(f"/api/skills/{skill_id}", json={"description": "x"}).status_code == 403


def test_edit_permission_allows_put_not_delete(client, regular_user, second_user,
                                               login, make_skill, grant):
    skill_id = make_skill(regular_user, "Editable Skill")
    grant(second_user, skill_id, "edit")
    login(second_user)
    assert client.put(f"/api/skills/{skill_id}", json={"description": "y"}).status_code == 200
    assert client.delete(f"/api/skills/{skill_id}").status_code == 403


def test_owner_can_delete(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Doomed Skill")
    login(regular_user)
    assert client.delete(f"/api/skills/{skill_id}").status_code == 200
    assert client.get(f"/api/skills/{skill_id}").status_code == 404


def test_admin_sees_and_edits_everything(client, admin_user, regular_user,
                                         login, make_skill):
    skill_id = make_skill(regular_user, "User Skill")
    login(admin_user)
    names = [s["name"] for s in client.get("/api/skills").get_json()]
    assert "User Skill" in names
    resp = client.get(f"/api/skills/{skill_id}")
    assert resp.get_json()["my_permission"] == "edit"
    assert client.put(f"/api/skills/{skill_id}", json={"description": "admin edit"}).status_code == 200
    assert client.delete(f"/api/skills/{skill_id}").status_code == 200


def test_list_search_and_filters(client, regular_user, login, make_skill):
    make_skill(regular_user, "Alpha Parser", tags=["pdf"], category="parsing",
               status="active", description="parses alpha files")
    make_skill(regular_user, "Beta Reporter", tags=["excel"], category="reporting",
               status="draft", description="builds beta reports")
    login(regular_user)

    assert len(client.get("/api/skills").get_json()) == 2
    hits = client.get("/api/skills?q=alpha").get_json()
    assert [s["name"] for s in hits] == ["Alpha Parser"]
    hits = client.get("/api/skills?tag=excel").get_json()
    assert [s["name"] for s in hits] == ["Beta Reporter"]
    hits = client.get("/api/skills?status=draft").get_json()
    assert [s["name"] for s in hits] == ["Beta Reporter"]
    hits = client.get("/api/skills?category=parsing").get_json()
    assert [s["name"] for s in hits] == ["Alpha Parser"]
    assert client.get("/api/skills?q=zzz").get_json() == []
