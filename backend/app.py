"""Application factory for the Skill Registry backend."""
import os

from flask import Flask, abort, jsonify, send_from_directory
from flask_login import LoginManager

from models import db, User

DIST_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
)


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

    @app.route("/")
    @app.route("/<path:path>")
    def spa(path=""):
        """Serve the built frontend with SPA fallback (demo/production mode)."""
        if path.startswith("api/"):
            abort(404)
        candidate = os.path.join(DIST_DIR, path)
        if path and os.path.isfile(candidate):
            return send_from_directory(DIST_DIR, path)
        if os.path.isfile(os.path.join(DIST_DIR, "index.html")):
            return send_from_directory(DIST_DIR, "index.html")
        abort(404, description="Frontend build not found. Run: cd frontend && npm run build")

    with app.app_context():
        db.create_all()
        _migrate_schema()

    return app


def _migrate_schema():
    """Add columns introduced after a database was first created.

    db.create_all() never alters existing tables, so databases from before
    the .skill upload feature lack the package columns on skill_versions.
    """
    existing = {
        row[1]
        for row in db.session.execute(db.text("PRAGMA table_info(skill_versions)"))
    }
    additions = {
        "package_blob": "BLOB",
        "package_filename": "VARCHAR(255)",
        "bundled_files": "JSON",
    }
    for column, ddl_type in additions.items():
        if column not in existing:
            db.session.execute(
                db.text(f"ALTER TABLE skill_versions ADD COLUMN {column} {ddl_type}")
            )
    db.session.commit()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5100"))
    create_app().run(port=port, debug=True)
