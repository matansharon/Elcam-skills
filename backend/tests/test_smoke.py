from sqlalchemy import inspect

from models import db, User


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_all_tables_exist(app):
    with app.app_context():
        names = set(inspect(db.engine).get_table_names())
        expected = {
            "users", "skills", "skill_versions",
            "skill_permissions", "skill_relationships", "audit_log",
        }
        assert expected <= names


def test_password_hashing_round_trip(app):
    with app.app_context():
        user = User(username="alice", display_name="Alice", role="admin")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        fetched = db.session.get(User, user.id)
        assert fetched.check_password("secret")
        assert not fetched.check_password("wrong")
        assert fetched.password_hash != "secret"
        assert fetched.to_dict()["role"] == "admin"
        assert "password_hash" not in fetched.to_dict()
