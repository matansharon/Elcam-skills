import pytest


@pytest.fixture()
def two_skills(regular_user, make_skill):
    a = make_skill(regular_user, "Skill A")
    b = make_skill(regular_user, "Skill B")
    return a, b


def _link(client, source, target, rel_type="depends_on"):
    return client.post("/api/relationships", json={
        "source_skill_id": source, "target_skill_id": target, "type": rel_type,
    })


def test_create_and_delete_relationship(client, regular_user, login, two_skills):
    a, b = two_skills
    login(regular_user)
    resp = _link(client, a, b, "depends_on")
    assert resp.status_code == 201
    rel = resp.get_json()
    assert rel["source"] == a and rel["target"] == b and rel["type"] == "depends_on"

    assert client.delete(f"/api/relationships/{rel['id']}").status_code == 200
    links = client.get(f"/api/skills/{a}/links").get_json()
    assert links["outgoing"] == [] and links["incoming"] == []


def test_self_link_rejected(client, regular_user, login, two_skills):
    a, _ = two_skills
    login(regular_user)
    assert _link(client, a, a).status_code == 400


def test_duplicate_rejected(client, regular_user, login, two_skills):
    a, b = two_skills
    login(regular_user)
    assert _link(client, a, b, "extends").status_code == 201
    assert _link(client, a, b, "extends").status_code == 400
    # same pair, different type is fine
    assert _link(client, a, b, "replaces").status_code == 201


def test_invalid_type_rejected(client, regular_user, login, two_skills):
    a, b = two_skills
    login(regular_user)
    assert _link(client, a, b, "friends_with").status_code == 400


def test_requires_edit_on_source(client, regular_user, second_user, login,
                                 two_skills, grant):
    a, b = two_skills
    grant(second_user, a, "read")
    grant(second_user, b, "read")
    login(second_user)
    assert _link(client, a, b).status_code == 403

    login(regular_user)
    rel_id = _link(client, a, b).get_json()["id"]
    login(second_user)
    assert client.delete(f"/api/relationships/{rel_id}").status_code == 403


def test_links_shows_both_directions(client, regular_user, login, make_skill):
    a = make_skill(regular_user, "Hub")
    b = make_skill(regular_user, "Upstream")
    c = make_skill(regular_user, "Downstream")
    login(regular_user)
    _link(client, a, b, "depends_on")
    _link(client, c, a, "extends")

    links = client.get(f"/api/skills/{a}/links").get_json()
    assert [(l["type"], l["skill"]["name"]) for l in links["outgoing"]] == [
        ("depends_on", "Upstream")]
    assert [(l["type"], l["skill"]["name"]) for l in links["incoming"]] == [
        ("extends", "Downstream")]


def test_graph_respects_visibility(client, regular_user, second_user, admin_user,
                                   login, make_skill, grant):
    a = make_skill(regular_user, "Visible A")
    b = make_skill(regular_user, "Visible B")
    c = make_skill(regular_user, "Secret C")
    login(regular_user)
    _link(client, a, b, "used_with")
    _link(client, b, c, "depends_on")

    # admin sees the full graph
    login(admin_user)
    graph = client.get("/api/graph").get_json()
    assert len(graph["nodes"]) == 3 and len(graph["edges"]) == 2

    # second_user sees only a and b, and only the edge between them
    grant(second_user, a, "read")
    grant(second_user, b, "read")
    login(second_user)
    graph = client.get("/api/graph").get_json()
    names = {n["name"] for n in graph["nodes"]}
    assert names == {"Visible A", "Visible B"}
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["type"] == "used_with"


def test_links_hide_invisible_endpoints(client, regular_user, second_user,
                                        login, make_skill, grant):
    a = make_skill(regular_user, "Shown")
    b = make_skill(regular_user, "NotShown")
    login(regular_user)
    _link(client, a, b, "depends_on")

    grant(second_user, a, "read")
    login(second_user)
    links = client.get(f"/api/skills/{a}/links").get_json()
    assert links["outgoing"] == []
