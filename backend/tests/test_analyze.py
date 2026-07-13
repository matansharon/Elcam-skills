import skills as skills_mod

CANNED = {"category": "data", "status": "active", "tags": ["pdf"], "related": []}


def _stub_ai(monkeypatch, app, capture=None):
    """Bypass the real Anthropic client and analyzer."""
    app.config["ANTHROPIC_API_KEY"] = "test-key"
    monkeypatch.setattr(skills_mod, "_anthropic_client", lambda: object())

    def fake_analyze(client, model, name, description, content, candidates):
        if capture is not None:
            capture["candidates"] = candidates
            capture["content"] = content
        return CANNED

    monkeypatch.setattr(skills_mod, "analyze_skill", fake_analyze)


def test_analyze_requires_login(client):
    resp = client.post("/api/skills/analyze", json={"content": "x"})
    assert resp.status_code == 401


def test_analyze_503_when_unconfigured(client, admin_user, login):
    login(admin_user)
    resp = client.post("/api/skills/analyze", json={"content": "some content"})
    assert resp.status_code == 503
    assert "not configured" in resp.get_json()["error"]


def test_analyze_400_when_empty(client, admin_user, login, app, monkeypatch):
    login(admin_user)
    _stub_ai(monkeypatch, app)
    resp = client.post("/api/skills/analyze", json={"content": "  ", "description": ""})
    assert resp.status_code == 400


def test_analyze_returns_suggestions(client, admin_user, login, app, monkeypatch):
    login(admin_user)
    _stub_ai(monkeypatch, app)
    resp = client.post("/api/skills/analyze", json={"content": "# Title\nbody"})
    assert resp.status_code == 200
    assert resp.get_json() == CANNED


def test_analyze_candidates_respect_rbac(
    client, admin_user, regular_user, login, app, monkeypatch, make_skill
):
    # admin owns one skill; regular_user can't see it.
    make_skill(admin_user, "Admin Only")
    mine = make_skill(regular_user, "Mine")
    login(regular_user)
    capture = {}
    _stub_ai(monkeypatch, app, capture)
    resp = client.post("/api/skills/analyze", json={"content": "hello"})
    assert resp.status_code == 200
    ids = {c["id"] for c in capture["candidates"]}
    assert ids == {mine}
