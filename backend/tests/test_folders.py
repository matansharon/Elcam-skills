def test_folder_crud_and_nesting(client, admin_user, login):
    login(admin_user)
    root = client.post("/api/folders", json={"name": "Backend"})
    assert root.status_code == 201
    root_id = root.get_json()["id"]

    child = client.post("/api/folders", json={"name": "Auth", "parent_id": root_id})
    assert child.status_code == 201

    tree = client.get("/api/folders").get_json()
    by_name = {f["name"]: f for f in tree}
    assert by_name["Auth"]["parent_id"] == root_id
    assert by_name["Backend"]["skill_count"] == 0

    # rename child
    child_id = by_name["Auth"]["id"]
    assert client.put(f"/api/folders/{child_id}", json={"name": "Authentication"}).status_code == 200

    # deleting parent cascades the child
    assert client.delete(f"/api/folders/{root_id}").status_code == 200
    assert client.get("/api/folders").get_json() == []


def test_duplicate_sibling_name_rejected(client, admin_user, login):
    login(admin_user)
    assert client.post("/api/folders", json={"name": "Dup"}).status_code == 201
    assert client.post("/api/folders", json={"name": "Dup"}).status_code == 400


def test_reparent_cycle_rejected(client, admin_user, login):
    login(admin_user)
    a = client.post("/api/folders", json={"name": "A"}).get_json()
    b = client.post("/api/folders", json={"name": "B", "parent_id": a["id"]}).get_json()
    # move A under its own descendant B -> cycle
    assert client.put(f"/api/folders/{a['id']}", json={"parent_id": b["id"]}).status_code == 400
    # move A under itself -> rejected
    assert client.put(f"/api/folders/{a['id']}", json={"parent_id": a["id"]}).status_code == 400


def test_folders_read_open_mutate_admin_only(client, admin_user, regular_user, login):
    login(admin_user)
    folder_id = client.post("/api/folders", json={"name": "Owned"}).get_json()["id"]

    login(regular_user)
    assert client.get("/api/folders").status_code == 200          # read allowed
    assert client.post("/api/folders", json={"name": "Nope"}).status_code == 403
    assert client.put(f"/api/folders/{folder_id}", json={"name": "X"}).status_code == 403
    assert client.delete(f"/api/folders/{folder_id}").status_code == 403


def test_reparent_to_root_does_not_delete_folder(client, admin_user, login):
    """Guards against `delete-orphan` on Folder.children accidentally
    deleting a reparented folder when parent_id is written directly."""
    login(admin_user)
    a = client.post("/api/folders", json={"name": "A"}).get_json()
    b = client.post("/api/folders", json={"name": "B", "parent_id": a["id"]}).get_json()

    resp = client.put(f"/api/folders/{b['id']}", json={"parent_id": None})
    assert resp.status_code == 200

    tree = client.get("/api/folders").get_json()
    by_name = {f["name"]: f for f in tree}
    assert "B" in by_name
    assert by_name["B"]["id"] == b["id"]
    assert by_name["B"]["parent_id"] is None


def test_set_and_move_membership(client, admin_user, login, make_skill):
    login(admin_user)
    skill_id = make_skill(admin_user, "Movable")
    a = client.post("/api/folders", json={"name": "A"}).get_json()
    b = client.post("/api/folders", json={"name": "B"}).get_json()

    # multi-membership via PUT
    client.put(f"/api/skills/{skill_id}/folders", json={"folder_ids": [a["id"], b["id"]]})
    folders = client.get(f"/api/skills/{skill_id}").get_json()["folders"]
    assert {f["id"] for f in folders} == {a["id"], b["id"]}

    tree = {f["name"]: f["skill_count"] for f in client.get("/api/folders").get_json()}
    assert tree["A"] == 1 and tree["B"] == 1

    # drag = move (exact single membership)
    client.put(f"/api/skills/{skill_id}/folders", json={"folder_ids": [a["id"]]})
    folders = client.get(f"/api/skills/{skill_id}").get_json()["folders"]
    assert {f["id"] for f in folders} == {a["id"]}

    # unfile
    client.put(f"/api/skills/{skill_id}/folders", json={"folder_ids": []})
    assert client.get(f"/api/skills/{skill_id}").get_json()["folders"] == []


def test_bulk_assign_move_and_add(client, admin_user, login, make_skill):
    login(admin_user)
    s1 = make_skill(admin_user, "S1")
    s2 = make_skill(admin_user, "S2")
    a = client.post("/api/folders", json={"name": "A"}).get_json()
    b = client.post("/api/folders", json={"name": "B"}).get_json()

    client.post(f"/api/folders/{a['id']}/skills", json={"skill_ids": [s1, s2], "mode": "move"})
    tree = {f["name"]: f["skill_count"] for f in client.get("/api/folders").get_json()}
    assert tree["A"] == 2

    client.post(f"/api/folders/{b['id']}/skills", json={"skill_ids": [s1], "mode": "add"})
    folders = {f["id"] for f in client.get(f"/api/skills/{s1}").get_json()["folders"]}
    assert folders == {a["id"], b["id"]}


def test_skills_folder_query_filter(client, admin_user, login, make_skill):
    login(admin_user)
    s1 = make_skill(admin_user, "In A")
    s2 = make_skill(admin_user, "Unfiled One")
    a = client.post("/api/folders", json={"name": "A"}).get_json()
    client.put(f"/api/skills/{s1}/folders", json={"folder_ids": [a["id"]]})

    in_a = [s["id"] for s in client.get(f"/api/skills?folder={a['id']}").get_json()]
    assert in_a == [s1]

    unfiled = [s["id"] for s in client.get("/api/skills?folder=unfiled").get_json()]
    assert s2 in unfiled and s1 not in unfiled


def test_membership_admin_only(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Owned")
    login(regular_user)
    assert client.put(f"/api/skills/{skill_id}/folders",
                      json={"folder_ids": []}).status_code == 403


def test_folder_skill_count_respects_viewer_visibility(client, admin_user, regular_user, login, make_skill):
    """The folder tree is visible to all, but skill_count reflects only the
    viewer's visible skills (not every membership in the folder)."""
    login(admin_user)
    skill_id = make_skill(admin_user, "Private")
    a = client.post("/api/folders", json={"name": "A"}).get_json()
    client.put(f"/api/skills/{skill_id}/folders", json={"folder_ids": [a["id"]]})

    tree = {f["name"]: f["skill_count"] for f in client.get("/api/folders").get_json()}
    assert tree["A"] == 1

    login(regular_user)
    tree = {f["name"]: f["skill_count"] for f in client.get("/api/folders").get_json()}
    assert tree["A"] == 0


def test_membership_invalid_inputs(client, admin_user, login, make_skill):
    login(admin_user)
    skill_id = make_skill(admin_user, "Bad Input Skill")
    folder = client.post("/api/folders", json={"name": "Box"}).get_json()
    # bad folder id in PUT body -> 400
    assert client.put(f"/api/skills/{skill_id}/folders",
                      json={"folder_ids": [999999]}).status_code == 400
    # non-list folder_ids -> 400
    assert client.put(f"/api/skills/{skill_id}/folders",
                      json={"folder_ids": "nope"}).status_code == 400
    # bulk: bad mode -> 400
    assert client.post(f"/api/folders/{folder['id']}/skills",
                       json={"skill_ids": [skill_id], "mode": "sideways"}).status_code == 400
    # bulk: bad skill id -> 400 (parity with set_skill_folders)
    assert client.post(f"/api/folders/{folder['id']}/skills",
                       json={"skill_ids": [999999], "mode": "move"}).status_code == 400
    # non-list skill_ids -> 400
    assert client.post(f"/api/folders/{folder['id']}/skills",
                       json={"skill_ids": "nope", "mode": "move"}).status_code == 400
