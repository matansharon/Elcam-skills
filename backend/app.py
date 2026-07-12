"""Application factory for the Skill Registry backend."""
import os

from flask import Flask, jsonify
from flask_login import LoginManager

from models import db, User


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object("config.Config")
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"error": "Authentication required"}), 401

    from auth import auth_bp
    from relationships import relationships_bp
    from skills import skills_bp
    from users import users_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(skills_bp)
    app.register_blueprint(relationships_bp)
    app.register_blueprint(users_bp)

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": getattr(e, "description", "Bad request")}), 400

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": getattr(e, "description", "Forbidden")}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": getattr(e, "description", "Not found")}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    create_app().run(port=5000, debug=True)
