import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load backend/.env if present so a developer can drop the key in a file
# instead of exporting it. Real environment variables still win.
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "skills.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AI-assisted skill analysis (optional; feature is inert without a key).
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    ANALYSIS_MODEL = os.environ.get("ANALYSIS_MODEL", "claude-sonnet-5")

    # Standalone activity-admin panel gate. When either is unset the panel
    # is disabled (login always fails). Independent of the DB user table.
    ADMIN_PANEL_USER = os.environ.get("ADMIN_PANEL_USER")
    ADMIN_PANEL_PASSWORD = os.environ.get("ADMIN_PANEL_PASSWORD")

    # Optional cap on stored activity rows; oldest are trimmed past it.
    # Unset/blank means keep everything.
    ACTIVITY_LOG_MAX_ROWS = (
        int(os.environ["ACTIVITY_LOG_MAX_ROWS"])
        if os.environ.get("ACTIVITY_LOG_MAX_ROWS")
        else None
    )
