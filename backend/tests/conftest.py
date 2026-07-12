import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app import create_app
from models import db, SkillPermission, User


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def _create_user(app, username, password, role):
    with app.app_context():
        user = User(username=username, display_name=username.capitalize(), role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return {"id": user.id, "username": username, "password": password, "role": role}


@pytest.fixture()
def admin_user(app):
    return _create_user(app, "admin", "admin123", "admin")


@pytest.fixture()
def regular_user(app):
    return _create_user(app, "dana", "dana123", "user")


@pytest.fixture()
def second_user(app):
    return _create_user(app, "yossi", "yossi123", "user")


@pytest.fixture()
def make_skill(app):
    def _make(owner, name, **kw):
        from services import create_skill
        with app.app_context():
            user = db.session.get(User, owner["id"])
            skill = create_skill(user, {
                "name": name,
                "description": kw.get("description", f"{name} description"),
                "category": kw.get("category", "general"),
                "tags": kw.get("tags", []),
                "status": kw.get("status", "active"),
                "content": kw.get("content", f"# {name}\n\nInitial content."),
            })
            return skill.id
    return _make


@pytest.fixture()
def grant(app):
    def _grant(user, skill_id, level):
        with app.app_context():
            db.session.add(
                SkillPermission(user_id=user["id"], skill_id=skill_id, level=level)
            )
            db.session.commit()
    return _grant


@pytest.fixture()
def login(client):
    def _login(user):
        resp = client.post(
            "/api/auth/login",
            json={"username": user["username"], "password": user["password"]},
        )
        assert resp.status_code == 200, resp.get_json()
        return resp
    return _login
