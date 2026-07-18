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
