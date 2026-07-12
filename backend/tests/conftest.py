import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app import create_app
from models import db, User


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
def login(client):
    def _login(user):
        resp = client.post(
            "/api/auth/login",
            json={"username": user["username"], "password": user["password"]},
        )
        assert resp.status_code == 200, resp.get_json()
        return resp
    return _login
