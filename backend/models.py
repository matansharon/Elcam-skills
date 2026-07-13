"""SQLAlchemy models for the Skill Registry."""
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

ROLES = ("admin", "user")
STATUSES = ("draft", "active", "deprecated")
PERMISSION_LEVELS = ("read", "edit")
RELATIONSHIP_TYPES = ("depends_on", "extends", "used_with", "replaces")


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="user")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }


class Skill(db.Model):
    __tablename__ = "skills"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="")
    tags = db.Column(db.JSON, nullable=False, default=list)
    status = db.Column(db.String(12), nullable=False, default="draft")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    owner = db.relationship("User", foreign_keys=[owner_id])
    versions = db.relationship(
        "SkillVersion", backref="skill",
        cascade="all, delete-orphan", lazy="dynamic",
    )
    permissions = db.relationship(
        "SkillPermission", backref="skill",
        cascade="all, delete-orphan", lazy="dynamic",
    )
    audit_entries = db.relationship(
        "AuditLog", backref="skill",
        cascade="all, delete-orphan", lazy="dynamic",
    )
    outgoing = db.relationship(
        "SkillRelationship", foreign_keys="SkillRelationship.source_skill_id",
        backref="source_skill", cascade="all, delete-orphan", lazy="dynamic",
    )
    incoming = db.relationship(
        "SkillRelationship", foreign_keys="SkillRelationship.target_skill_id",
        backref="target_skill", cascade="all, delete-orphan", lazy="dynamic",
    )

    @property
    def current_version(self):
        latest = self.versions.order_by(SkillVersion.version_number.desc()).first()
        return latest.version_number if latest else 0

    def to_dict(self, my_permission=None):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner": {"id": self.owner.id, "display_name": self.owner.display_name},
            "category": self.category,
            "tags": self.tags or [],
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_version": self.current_version,
            "my_permission": my_permission,
        }


class SkillVersion(db.Model):
    __tablename__ = "skill_versions"
    __table_args__ = (db.UniqueConstraint("skill_id", "version_number"),)

    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    category = db.Column(db.String(80), nullable=False, default="")
    tags = db.Column(db.JSON, nullable=False, default=list)
    status = db.Column(db.String(12), nullable=False, default="draft")
    content = db.Column(db.Text, nullable=False, default="")
    change_note = db.Column(db.String(500), nullable=False, default="")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    # Set only on versions created from an uploaded .skill package.
    package_blob = db.Column(db.LargeBinary, nullable=True)
    package_filename = db.Column(db.String(255), nullable=True)
    bundled_files = db.Column(db.JSON, nullable=True)

    author = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self, include_content=True):
        data = {
            "version_number": self.version_number,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags or [],
            "status": self.status,
            "change_note": self.change_note,
            "created_by": self.author.display_name,
            "created_at": self.created_at.isoformat(),
            "has_package": self.package_blob is not None,
            "package_filename": self.package_filename,
            "bundled_files": self.bundled_files or [],
        }
        if include_content:
            data["content"] = self.content
        return data


class SkillPermission(db.Model):
    __tablename__ = "skill_permissions"
    __table_args__ = (db.UniqueConstraint("user_id", "skill_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    level = db.Column(db.String(10), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])


class SkillRelationship(db.Model):
    __tablename__ = "skill_relationships"
    __table_args__ = (
        db.UniqueConstraint("source_skill_id", "target_skill_id", "type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    source_skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    target_skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source_skill_id,
            "target": self.target_skill_id,
            "type": self.type,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(30), nullable=False)
    detail = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "action": self.action,
            "detail": self.detail,
            "user": self.user.display_name if self.user else None,
            "created_at": self.created_at.isoformat(),
        }


class ActivityLog(db.Model):
    """Global, app-wide activity log: one row per API request.

    Distinct from AuditLog (which is per-skill). `actor` is denormalized
    because failed logins have no user and the .env panel admin is not a
    DB row.
    """
    __tablename__ = "activity_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    actor = db.Column(db.String(120), nullable=False, default="anonymous")
    method = db.Column(db.String(10), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)
    duration_ms = db.Column(db.Integer, nullable=False, default=0)
    ip_address = db.Column(db.String(45), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(20), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "actor": self.actor,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "ip_address": self.ip_address,
            "summary": self.summary,
            "category": self.category,
        }
