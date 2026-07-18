# User Pages, Favorites & Folders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-user pages (owned skills + favorites), private per-user favorites, and a global admin-managed hierarchical folder tree with drag-and-drop and multi-folder membership.

**Architecture:** Three new SQLAlchemy tables — `Folder` (self-referential for subfolders), `SkillFolder` (many-to-many join), `Favorite` (per-user) — created automatically by the existing `db.create_all()`. Backend logic lives in `services.py` behind plain functions; blueprints stay thin (a new `folders.py`, a new `favorites.py`, plus additions to `skills.py` and `users.py`). The React frontend gains a `FavoriteStar` component, a `FolderTree` sidebar on the Dashboard, and a `UserPage` route.

**Tech Stack:** Flask, Flask-Login, SQLAlchemy (SQLite), pytest (backend); React 18, react-router-dom 6, Vite (frontend). No frontend test runner exists — frontend tasks gate on `npm run build` compiling plus manual browser verification.

## Global Constraints

- **Python interpreter:** `C:\Users\Matan\AppData\Local\Programs\Python\Python310\python.exe` (invoke as `.venv\Scripts\python.exe` from the repo root). Use `python`, never `python3`.
- **Backend tests:** `.venv\Scripts\python.exe -m pytest backend\tests -q` (run from repo root).
- **Frontend build:** from `frontend\`, `npm run build`.
- **Dev server:** `run_dev.bat` (Flask :5100, Vite :5173). App port 5100 (not 5000).
- **Commits carry NO AI attribution** (repo convention — see existing `git log`). Do not add `Co-Authored-By`.
- **RBAC unchanged:** skill visibility is governed by `visible_skills(user)` / `get_visible_skill_or_404`. Invisible == 404. Do not weaken this.
- **Blueprint pattern:** routes stay thin; all data logic goes in `backend/services.py`. Admin gating inside a route is `require_admin(current_user)` (aborts 403), mirroring the existing `require_edit`.
- **New tables need no migration code:** `db.create_all()` in `create_app()` creates them. `_migrate_schema()` only adds *columns* to pre-existing tables — leave it alone.

---

## File Structure

**Backend (new):**
- `backend/folders.py` — folders blueprint (`/api/folders` CRUD + bulk skill assignment).
- `backend/favorites.py` — favorites blueprint (`/api/favorites`, `/api/skills/:id/favorite`).
- `backend/tests/test_folders.py`, `test_favorites.py`, `test_user_page.py`, `test_folder_models.py`.

**Backend (modified):**
- `backend/models.py` — add `Folder`, `SkillFolder`, `Favorite`; add relationships to `Skill`/`User`; add `favorited` to `Skill.to_dict`.
- `backend/services.py` — add favorites, folder, and membership helpers + `require_admin`.
- `backend/skills.py` — add `favorited` to serialization, a `folder` list filter, membership endpoint, folders in detail.
- `backend/users.py` — add `GET /api/users/:id` and `/favorites` (self-or-admin).
- `backend/app.py` — register the two new blueprints.
- `backend/seed.py` — (optional, Task 10) demo folders + favorites.

**Frontend (new):**
- `frontend/src/components/FavoriteStar.jsx`
- `frontend/src/components/FolderTree.jsx`
- `frontend/src/components/FolderMenu.jsx`
- `frontend/src/pages/UserPage.jsx`

**Frontend (modified):**
- `frontend/src/pages/Dashboard.jsx` — sidebar layout, folder filter, star column, admin controls.
- `frontend/src/pages/SkillDetail.jsx` — favorite star in header.
- `frontend/src/App.jsx` — `/users/:id` route + "My Page" nav link.
- `frontend/src/styles.css` — styles for star, folder tree, folder menu, user page.

---

## Task 1: New models (Folder, SkillFolder, Favorite) + cascades

**Files:**
- Modify: `backend/models.py`
- Test: `backend/tests/test_folder_models.py`

**Interfaces:**
- Produces: `Folder(name, parent_id, created_by)` with `.to_dict(skill_count=0) -> {id, name, parent_id, skill_count}`; `SkillFolder(skill_id, folder_id)`; `Favorite(user_id, skill_id)`. `Skill.to_dict(my_permission=None, favorited=False)`. Cascades: deleting a skill removes its `SkillFolder` + `Favorite` rows; deleting a folder deletes subfolders recursively + removes its `SkillFolder` rows (skills survive); deleting a user removes their `Favorite` rows.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_folder_models.py`:

```python
from models import db, Folder, SkillFolder, Favorite, Skill


def test_deleting_skill_cascades_membership_and_favorites(app, admin_user, make_skill):
    skill_id = make_skill(admin_user, "Cascade Skill")
    with app.app_context():
        folder = Folder(name="F", created_by=admin_user["id"])
        db.session.add(folder)
        db.session.flush()
        db.session.add(SkillFolder(skill_id=skill_id, folder_id=folder.id))
        db.session.add(Favorite(user_id=admin_user["id"], skill_id=skill_id))
        db.session.commit()

        db.session.delete(db.session.get(Skill, skill_id))
        db.session.commit()

        assert SkillFolder.query.count() == 0
        assert Favorite.query.count() == 0
        assert Folder.query.count() == 1  # folder itself survives


def test_deleting_folder_cascades_subfolders_but_keeps_skills(app, admin_user, make_skill):
    skill_id = make_skill(admin_user, "Kept Skill")
    with app.app_context():
        parent = Folder(name="Parent", created_by=admin_user["id"])
        db.session.add(parent)
        db.session.flush()
        child = Folder(name="Child", parent_id=parent.id, created_by=admin_user["id"])
        db.session.add(child)
        db.session.flush()
        db.session.add(SkillFolder(skill_id=skill_id, folder_id=child.id))
        db.session.commit()

        db.session.delete(db.session.get(Folder, parent.id))
        db.session.commit()

        assert Folder.query.count() == 0        # parent + child both gone
        assert SkillFolder.query.count() == 0    # membership gone
        assert db.session.get(Skill, skill_id) is not None  # skill survives


def test_deleting_user_cascades_favorites(app, admin_user, regular_user, make_skill):
    from models import User
    skill_id = make_skill(admin_user, "Shared Skill")
    with app.app_context():
        db.session.add(Favorite(user_id=regular_user["id"], skill_id=skill_id))
        db.session.commit()
        db.session.delete(db.session.get(User, regular_user["id"]))
        db.session.commit()
        assert Favorite.query.count() == 0
        assert db.session.get(Skill, skill_id) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest backend\tests\test_folder_models.py -q`
Expected: FAIL with `ImportError: cannot import name 'Folder' from 'models'`.

- [ ] **Step 3: Add the three models**

In `backend/models.py`, after the `SkillRelationship` class (before `AuditLog`), add:

```python
class Folder(db.Model):
    __tablename__ = "folders"
    __table_args__ = (db.UniqueConstraint("parent_id", "name"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("folders.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    children = db.relationship(
        "Folder",
        backref=db.backref("parent", remote_side=[id]),
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    skill_links = db.relationship(
        "SkillFolder", backref="folder",
        cascade="all, delete-orphan", lazy="dynamic",
    )

    def to_dict(self, skill_count=0):
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "skill_count": skill_count,
        }


class SkillFolder(db.Model):
    __tablename__ = "skill_folders"
    __table_args__ = (db.UniqueConstraint("skill_id", "folder_id"),)

    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey("folders.id"), nullable=False)


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (db.UniqueConstraint("user_id", "skill_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
```

- [ ] **Step 4: Add cascade relationships on `Skill` and `User`**

In `backend/models.py`, inside `class Skill`, after the `incoming = db.relationship(...)` block (around line 83), add:

```python
    folder_links = db.relationship(
        "SkillFolder", backref="skill",
        cascade="all, delete-orphan", lazy="dynamic",
    )
    favorited_by = db.relationship(
        "Favorite", backref="skill",
        cascade="all, delete-orphan", lazy="dynamic",
    )
```

Inside `class User`, after the `created_at = db.Column(...)` line (around line 28), add:

```python
    favorites = db.relationship(
        "Favorite", backref="user",
        cascade="all, delete-orphan", lazy="dynamic",
    )
```

- [ ] **Step 5: Add `favorited` to `Skill.to_dict`**

In `backend/models.py`, change the `Skill.to_dict` signature and return dict:

```python
    def to_dict(self, my_permission=None, favorited=False):
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
            "favorited": favorited,
        }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest backend\tests\test_folder_models.py -q`
Expected: PASS (3 passed).

- [ ] **Step 7: Run the full backend suite (nothing regressed)**

Run: `.venv\Scripts\python.exe -m pytest backend\tests -q`
Expected: all pass (existing tests still green — `favorited` is additive).

- [ ] **Step 8: Commit**

```bash
git add backend/models.py backend/tests/test_folder_models.py
git commit -m "feat: Folder, SkillFolder, Favorite models with cascades"
```

---

## Task 2: Favorites service + blueprint + serialization flag

**Files:**
- Modify: `backend/services.py`, `backend/skills.py`, `backend/app.py`
- Create: `backend/favorites.py`, `backend/tests/test_favorites.py`

**Interfaces:**
- Consumes: `visible_skills`, `get_visible_skill_or_404`, `get_permission_level` (existing in `services.py`); `Favorite` (Task 1).
- Produces: services `favorite_skill_ids(user) -> set[int]`, `toggle_favorite(user, skill, on: bool) -> None`, `visible_favorites(user) -> list[Skill]`, `favorites_of(target_user, viewer) -> list[Skill]`. Endpoints `GET /api/favorites`, `PUT/DELETE /api/skills/:id/favorite`. `skill.to_dict` now emits `favorited` for the current user in list + detail.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_favorites.py`:

```python
def test_favorite_toggle_and_list(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Fav Skill")
    login(regular_user)

    assert client.get(f"/api/skills/{skill_id}").get_json()["favorited"] is False
    assert client.put(f"/api/skills/{skill_id}/favorite").get_json() == {"favorited": True}
    assert client.get(f"/api/skills/{skill_id}").get_json()["favorited"] is True

    favs = client.get("/api/favorites").get_json()
    assert [s["id"] for s in favs] == [skill_id]
    assert favs[0]["favorited"] is True

    # idempotent add
    assert client.put(f"/api/skills/{skill_id}/favorite").get_json() == {"favorited": True}
    assert len(client.get("/api/favorites").get_json()) == 1

    # remove
    assert client.delete(f"/api/skills/{skill_id}/favorite").get_json() == {"favorited": False}
    assert client.get("/api/favorites").get_json() == []


def test_cannot_favorite_invisible_skill(client, regular_user, second_user, login, make_skill):
    skill_id = make_skill(regular_user, "Private Skill")
    login(second_user)
    assert client.put(f"/api/skills/{skill_id}/favorite").status_code == 404


def test_favorites_filtered_by_visibility(client, admin_user, regular_user, second_user,
                                           login, make_skill, grant):
    skill_id = make_skill(regular_user, "Shared Then Revoked")
    grant(second_user, skill_id, "read")

    login(second_user)
    client.put(f"/api/skills/{skill_id}/favorite")
    assert len(client.get("/api/favorites").get_json()) == 1

    login(admin_user)
    client.put(f"/api/users/{second_user['id']}/permissions/{skill_id}", json={"level": None})

    login(second_user)
    assert client.get("/api/favorites").get_json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest backend\tests\test_favorites.py -q`
Expected: FAIL — `favorited` KeyError or 404 on `/api/favorites` (no route yet).

- [ ] **Step 3: Add favorites helpers to `services.py`**

In `backend/services.py`, update the models import to include `Favorite`:

```python
from models import (
    RELATIONSHIP_TYPES,
    STATUSES,
    AuditLog,
    Favorite,
    Skill,
    SkillPermission,
    SkillRelationship,
    SkillVersion,
    db,
    utcnow,
)
```

Then add, after the `require_edit` function (around line 69):

```python
def require_admin(user):
    if not user.is_admin:
        abort(403, description="Admin access required")


# --- favorites -------------------------------------------------------------

def favorite_skill_ids(user):
    return {f.skill_id for f in Favorite.query.filter_by(user_id=user.id)}


def toggle_favorite(user, skill, on):
    existing = Favorite.query.filter_by(user_id=user.id, skill_id=skill.id).first()
    if on and existing is None:
        db.session.add(Favorite(user_id=user.id, skill_id=skill.id))
    elif not on and existing is not None:
        db.session.delete(existing)
    db.session.commit()


def favorites_of(target_user, viewer):
    """Skills favorited by target_user, filtered to viewer's visibility."""
    fav_ids = {f.skill_id for f in Favorite.query.filter_by(user_id=target_user.id)}
    return [s for s in visible_skills(viewer) if s.id in fav_ids]


def visible_favorites(user):
    return favorites_of(user, user)
```

- [ ] **Step 4: Create the favorites blueprint**

Create `backend/favorites.py`:

```python
"""Favorites blueprint: per-user favorite skills (private to each user)."""
from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from services import (
    get_permission_level,
    get_visible_skill_or_404,
    toggle_favorite,
    visible_favorites,
)

favorites_bp = Blueprint("favorites", __name__, url_prefix="/api")


@favorites_bp.get("/favorites")
@login_required
def list_favorites():
    skills = visible_favorites(current_user)
    skills.sort(key=lambda s: s.updated_at, reverse=True)
    return jsonify([
        s.to_dict(my_permission=get_permission_level(current_user, s), favorited=True)
        for s in skills
    ])


@favorites_bp.put("/skills/<int:skill_id>/favorite")
@login_required
def add_favorite(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    toggle_favorite(current_user, skill, on=True)
    return jsonify({"favorited": True})


@favorites_bp.delete("/skills/<int:skill_id>/favorite")
@login_required
def remove_favorite(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    toggle_favorite(current_user, skill, on=False)
    return jsonify({"favorited": False})
```

- [ ] **Step 5: Register the blueprint**

In `backend/app.py`, inside `create_app`, add to the blueprint imports/registration block (around lines 33-42):

```python
    from favorites import favorites_bp
    app.register_blueprint(favorites_bp)
```

- [ ] **Step 6: Emit `favorited` in the skills list serialization**

In `backend/skills.py`, update the services import block to add `favorite_skill_ids`:

```python
from services import (
    create_skill,
    create_skill_from_package,
    create_version_from_package,
    delete_skill,
    favorite_skill_ids,
    get_permission_level,
    get_visible_skill_or_404,
    require_edit,
    restore_version,
    update_skill,
    visible_skills,
)
```

In `list_skills`, compute the favorite set once and pass it per skill. Replace the loop body's `result.append(...)` and add `fav_ids` above the loop:

```python
    fav_ids = favorite_skill_ids(current_user)
    result = []
    for skill in visible_skills(current_user):
        if q and q not in skill.name.lower() and q not in (skill.description or "").lower():
            continue
        if tag and tag not in (skill.tags or []):
            continue
        if category and skill.category != category:
            continue
        if status and skill.status != status:
            continue
        if owner and str(skill.owner_id) != owner and skill.owner.display_name != owner:
            continue
        result.append(
            skill.to_dict(
                my_permission=get_permission_level(current_user, skill),
                favorited=skill.id in fav_ids,
            )
        )
```

In `get_skill`, pass `favorited`:

```python
@skills_bp.get("/<int:skill_id>")
@login_required
def get_skill(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    fav_ids = favorite_skill_ids(current_user)
    return jsonify(
        skill.to_dict(
            my_permission=get_permission_level(current_user, skill),
            favorited=skill.id in fav_ids,
        )
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest backend\tests\test_favorites.py -q`
Expected: PASS (3 passed).

- [ ] **Step 8: Run the full backend suite**

Run: `.venv\Scripts\python.exe -m pytest backend\tests -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add backend/services.py backend/skills.py backend/app.py backend/favorites.py backend/tests/test_favorites.py
git commit -m "feat: per-user favorites API and favorited flag on skills"
```

---

## Task 3: Folders CRUD service + blueprint

**Files:**
- Modify: `backend/services.py`, `backend/app.py`
- Create: `backend/folders.py`, `backend/tests/test_folders.py`

**Interfaces:**
- Consumes: `require_admin`, `visible_skills` (services); `Folder`, `SkillFolder` (models).
- Produces: services `get_folder_or_404(folder_id) -> Folder`, `create_folder(user, name, parent_id) -> Folder`, `update_folder(user, folder, name=_UNSET, parent_id=_UNSET) -> Folder`, `delete_folder(user, folder) -> None`, `visible_folder_tree(user) -> list[dict]`. Endpoints `GET /api/folders`, `POST /api/folders`, `PUT /api/folders/:id`, `DELETE /api/folders/:id`. (The `POST /api/folders/:id/skills` bulk endpoint is added in Task 4.)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_folders.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest backend\tests\test_folders.py -q`
Expected: FAIL — 404 on `/api/folders` (no blueprint yet).

- [ ] **Step 3: Add folder helpers to `services.py`**

In `backend/services.py`, update the models import to also include `Folder` and `SkillFolder`:

```python
from models import (
    RELATIONSHIP_TYPES,
    STATUSES,
    AuditLog,
    Favorite,
    Folder,
    Skill,
    SkillFolder,
    SkillPermission,
    SkillRelationship,
    SkillVersion,
    db,
    utcnow,
)
```

At the top of the file, after the imports, add a sentinel:

```python
_UNSET = object()
```

Then add a folders section (place it after the favorites helpers from Task 2):

```python
# --- folders ---------------------------------------------------------------

def get_folder_or_404(folder_id):
    folder = db.session.get(Folder, folder_id)
    if folder is None:
        abort(404, description="Folder not found")
    return folder


def _sibling_name_taken(name, parent_id, exclude_id=None):
    q = Folder.query.filter_by(name=name, parent_id=parent_id)
    if exclude_id is not None:
        q = q.filter(Folder.id != exclude_id)
    return q.first() is not None


def _would_create_cycle(folder, new_parent_id):
    """True if making new_parent_id the parent of `folder` forms a cycle."""
    current_id = new_parent_id
    while current_id is not None:
        if current_id == folder.id:
            return True
        parent = db.session.get(Folder, current_id)
        current_id = parent.parent_id if parent else None
    return False


def create_folder(user, name, parent_id):
    name = (name or "").strip()
    if not name:
        abort(400, description="Folder name is required")
    if parent_id is not None and db.session.get(Folder, parent_id) is None:
        abort(400, description="Parent folder not found")
    if _sibling_name_taken(name, parent_id):
        abort(400, description="A folder with this name already exists here")
    folder = Folder(name=name, parent_id=parent_id, created_by=user.id)
    db.session.add(folder)
    db.session.commit()
    return folder


def update_folder(user, folder, name=_UNSET, parent_id=_UNSET):
    new_name = folder.name if name is _UNSET else (name or "").strip()
    if not new_name:
        abort(400, description="Folder name is required")
    new_parent_id = folder.parent_id if parent_id is _UNSET else parent_id
    if parent_id is not _UNSET and parent_id is not None:
        if db.session.get(Folder, parent_id) is None:
            abort(400, description="Parent folder not found")
        if _would_create_cycle(folder, parent_id):
            abort(400, description="Cannot move a folder into itself or a descendant")
    if _sibling_name_taken(new_name, new_parent_id, exclude_id=folder.id):
        abort(400, description="A folder with this name already exists here")
    folder.name = new_name
    folder.parent_id = new_parent_id
    db.session.commit()
    return folder


def delete_folder(user, folder):
    db.session.delete(folder)  # cascade removes subfolders + memberships
    db.session.commit()


def visible_folder_tree(user):
    """All folders as a flat list; skill_count counts memberships whose skill
    is visible to `user`. The frontend nests by parent_id."""
    visible_ids = {s.id for s in visible_skills(user)}
    counts = {}
    for link in SkillFolder.query.all():
        if link.skill_id in visible_ids:
            counts[link.folder_id] = counts.get(link.folder_id, 0) + 1
    folders = Folder.query.order_by(Folder.name).all()
    return [f.to_dict(skill_count=counts.get(f.id, 0)) for f in folders]
```

- [ ] **Step 4: Create the folders blueprint**

Create `backend/folders.py`:

```python
"""Folders blueprint: one global, admin-managed folder tree.

Reading the tree is open to any logged-in user (read-only navigation);
every mutation requires admin.
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from services import (
    create_folder,
    delete_folder,
    get_folder_or_404,
    require_admin,
    update_folder,
    visible_folder_tree,
)

folders_bp = Blueprint("folders", __name__, url_prefix="/api/folders")


@folders_bp.get("")
@login_required
def list_folders():
    return jsonify(visible_folder_tree(current_user))


@folders_bp.post("")
@login_required
def create():
    require_admin(current_user)
    data = request.get_json(silent=True) or {}
    folder = create_folder(current_user, data.get("name"), data.get("parent_id"))
    return jsonify(folder.to_dict(skill_count=0)), 201


@folders_bp.put("/<int:folder_id>")
@login_required
def update(folder_id):
    require_admin(current_user)
    folder = get_folder_or_404(folder_id)
    data = request.get_json(silent=True) or {}
    kwargs = {}
    if "name" in data:
        kwargs["name"] = data["name"]
    if "parent_id" in data:
        kwargs["parent_id"] = data["parent_id"]
    update_folder(current_user, folder, **kwargs)
    return jsonify(folder.to_dict())


@folders_bp.delete("/<int:folder_id>")
@login_required
def delete(folder_id):
    require_admin(current_user)
    folder = get_folder_or_404(folder_id)
    delete_folder(current_user, folder)
    return jsonify({"status": "deleted"})
```

- [ ] **Step 5: Register the blueprint**

In `backend/app.py`, inside `create_app`, add:

```python
    from folders import folders_bp
    app.register_blueprint(folders_bp)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest backend\tests\test_folders.py -q`
Expected: PASS (4 passed).

- [ ] **Step 7: Run the full backend suite**

Run: `.venv\Scripts\python.exe -m pytest backend\tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/services.py backend/folders.py backend/app.py backend/tests/test_folders.py
git commit -m "feat: global admin-managed folder tree CRUD"
```

---

## Task 4: Skill↔folder membership + folder filter + folders in detail

**Files:**
- Modify: `backend/services.py`, `backend/skills.py`, `backend/folders.py`
- Test: `backend/tests/test_folders.py` (append)

**Interfaces:**
- Consumes: `Folder`, `SkillFolder`, `Skill` (models); `require_admin`, `get_visible_skill_or_404`, `get_folder_or_404` (services).
- Produces: services `set_skill_folders(skill, folder_ids) -> None`, `bulk_assign(folder, skill_ids, mode) -> None`, `skill_folders(skill) -> list[{id, name}]`. Endpoints `PUT /api/skills/:id/folders {folder_ids}`, `POST /api/folders/:id/skills {skill_ids, mode}`. `GET /api/skills?folder=<id|unfiled>` filter. Skill detail response gains `folders`.

- [ ] **Step 1: Write the failing tests (append to `test_folders.py`)**

```python
def test_set_and_move_membership(client, admin_user, login, make_skill):
    login(admin_user)
    skill_id = make_skill(admin_user, "Movable")
    a = client.post("/api/folders", json={"name": "A"}).get_json()
    b = client.post("/api/folders", json={"name": "B"}).get_json()

    # multi-membership via PUT
    client.put(f"/api/skills/{skill_id}/folders", json={"folder_ids": [a["id"], b["id"]]})
    folders = client.get(f"/api/skills/{skill_id}").get_json()["folders"]
    assert {f["id"] for f in folders} == {a["id"], b["id"]}

    tree = {f["name"]: f["skill_count"] for f in client.get("/api/folders").get_json()}
    assert tree["A"] == 1 and tree["B"] == 1

    # drag = move (exact single membership)
    client.put(f"/api/skills/{skill_id}/folders", json={"folder_ids": [a["id"]]})
    folders = client.get(f"/api/skills/{skill_id}").get_json()["folders"]
    assert {f["id"] for f in folders} == {a["id"]}

    # unfile
    client.put(f"/api/skills/{skill_id}/folders", json={"folder_ids": []})
    assert client.get(f"/api/skills/{skill_id}").get_json()["folders"] == []


def test_bulk_assign_move_and_add(client, admin_user, login, make_skill):
    login(admin_user)
    s1 = make_skill(admin_user, "S1")
    s2 = make_skill(admin_user, "S2")
    a = client.post("/api/folders", json={"name": "A"}).get_json()
    b = client.post("/api/folders", json={"name": "B"}).get_json()

    client.post(f"/api/folders/{a['id']}/skills", json={"skill_ids": [s1, s2], "mode": "move"})
    tree = {f["name"]: f["skill_count"] for f in client.get("/api/folders").get_json()}
    assert tree["A"] == 2

    client.post(f"/api/folders/{b['id']}/skills", json={"skill_ids": [s1], "mode": "add"})
    folders = {f["id"] for f in client.get(f"/api/skills/{s1}").get_json()["folders"]}
    assert folders == {a["id"], b["id"]}


def test_skills_folder_query_filter(client, admin_user, login, make_skill):
    login(admin_user)
    s1 = make_skill(admin_user, "In A")
    s2 = make_skill(admin_user, "Unfiled One")
    a = client.post("/api/folders", json={"name": "A"}).get_json()
    client.put(f"/api/skills/{s1}/folders", json={"folder_ids": [a["id"]]})

    in_a = [s["id"] for s in client.get(f"/api/skills?folder={a['id']}").get_json()]
    assert in_a == [s1]

    unfiled = [s["id"] for s in client.get("/api/skills?folder=unfiled").get_json()]
    assert s2 in unfiled and s1 not in unfiled


def test_membership_admin_only(client, regular_user, login, make_skill):
    skill_id = make_skill(regular_user, "Owned")
    login(regular_user)
    assert client.put(f"/api/skills/{skill_id}/folders",
                      json={"folder_ids": []}).status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest backend\tests\test_folders.py -q`
Expected: FAIL — `KeyError: 'folders'` / 404 on the new routes.

- [ ] **Step 3: Add membership helpers to `services.py`**

Add after the folders section:

```python
def skill_folders(skill):
    """List of {id, name} for the folders this skill belongs to."""
    result = []
    for link in SkillFolder.query.filter_by(skill_id=skill.id):
        folder = db.session.get(Folder, link.folder_id)
        if folder is not None:
            result.append({"id": folder.id, "name": folder.name})
    return result


def set_skill_folders(skill, folder_ids):
    """Replace the skill's folder memberships with exactly folder_ids."""
    ids = list(dict.fromkeys(folder_ids or []))  # de-dupe, keep order
    for fid in ids:
        if db.session.get(Folder, fid) is None:
            abort(400, description=f"Folder {fid} not found")
    SkillFolder.query.filter_by(skill_id=skill.id).delete()
    for fid in ids:
        db.session.add(SkillFolder(skill_id=skill.id, folder_id=fid))
    db.session.commit()


def bulk_assign(folder, skill_ids, mode):
    """mode 'move' sets each skill's membership to exactly [folder]; mode
    'add' adds folder to each skill's existing memberships."""
    if mode not in ("move", "add"):
        abort(400, description="mode must be 'move' or 'add'")
    for sid in skill_ids or []:
        if db.session.get(Skill, sid) is None:
            abort(404, description=f"Skill {sid} not found")
        if mode == "move":
            SkillFolder.query.filter_by(skill_id=sid).delete()
            db.session.add(SkillFolder(skill_id=sid, folder_id=folder.id))
        else:
            exists = SkillFolder.query.filter_by(
                skill_id=sid, folder_id=folder.id).first()
            if exists is None:
                db.session.add(SkillFolder(skill_id=sid, folder_id=folder.id))
    db.session.commit()
```

- [ ] **Step 4: Add the membership + detail changes to `skills.py`**

Update imports at the top of `backend/skills.py`. Change the models import:

```python
from models import AuditLog, SkillFolder, SkillVersion, db
```

Add to the services import block: `require_admin`, `set_skill_folders`, `skill_folders`:

```python
from services import (
    create_skill,
    create_skill_from_package,
    create_version_from_package,
    delete_skill,
    favorite_skill_ids,
    get_permission_level,
    get_visible_skill_or_404,
    require_admin,
    require_edit,
    restore_version,
    set_skill_folders,
    skill_folders,
    update_skill,
    visible_skills,
)
```

Add the `folder` query filter to `list_skills`. After the line `status = (request.args.get("status") or "").strip()`, add:

```python
    folder = (request.args.get("folder") or "").strip()

    folder_filter = None  # None | ("include", set) | ("exclude", set)
    if folder == "unfiled":
        filed = {row[0] for row in db.session.query(SkillFolder.skill_id).distinct()}
        folder_filter = ("exclude", filed)
    elif folder:
        try:
            fid = int(folder)
        except ValueError:
            abort(400, description="folder must be an id or 'unfiled'")
        member = {row[0] for row in
                  db.session.query(SkillFolder.skill_id).filter_by(folder_id=fid)}
        folder_filter = ("include", member)
```

Then inside the loop, after the `owner` filter check and before `result.append(...)`, add:

```python
        if folder_filter is not None:
            fmode, fids = folder_filter
            if fmode == "include" and skill.id not in fids:
                continue
            if fmode == "exclude" and skill.id in fids:
                continue
```

Add `folders` to the detail response. Update `get_skill`:

```python
@skills_bp.get("/<int:skill_id>")
@login_required
def get_skill(skill_id):
    skill = get_visible_skill_or_404(current_user, skill_id)
    fav_ids = favorite_skill_ids(current_user)
    data = skill.to_dict(
        my_permission=get_permission_level(current_user, skill),
        favorited=skill.id in fav_ids,
    )
    data["folders"] = skill_folders(skill)
    return jsonify(data)
```

Add the membership endpoint (place after `get_skill`):

```python
@skills_bp.put("/<int:skill_id>/folders")
@login_required
def set_folders(skill_id):
    require_admin(current_user)
    skill = get_visible_skill_or_404(current_user, skill_id)
    data = request.get_json(silent=True) or {}
    folder_ids = data.get("folder_ids", [])
    if not isinstance(folder_ids, list):
        abort(400, description="folder_ids must be a list")
    set_skill_folders(skill, folder_ids)
    return jsonify({"folders": skill_folders(skill)})
```

- [ ] **Step 5: Add the bulk-assign endpoint to `folders.py`**

In `backend/folders.py`, add `bulk_assign` to the services import, and add the route:

```python
from services import (
    bulk_assign,
    create_folder,
    delete_folder,
    get_folder_or_404,
    require_admin,
    update_folder,
    visible_folder_tree,
)
```

```python
@folders_bp.post("/<int:folder_id>/skills")
@login_required
def assign_skills(folder_id):
    require_admin(current_user)
    folder = get_folder_or_404(folder_id)
    data = request.get_json(silent=True) or {}
    skill_ids = data.get("skill_ids", [])
    if not isinstance(skill_ids, list):
        abort(400, description="skill_ids must be a list")
    bulk_assign(folder, skill_ids, data.get("mode", "move"))
    return jsonify({"status": "ok"})
```

Add `abort` to the flask import in `folders.py`:

```python
from flask import Blueprint, abort, jsonify, request
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest backend\tests\test_folders.py -q`
Expected: PASS (all folder tests green).

- [ ] **Step 7: Run the full backend suite**

Run: `.venv\Scripts\python.exe -m pytest backend\tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/services.py backend/skills.py backend/folders.py backend/tests/test_folders.py
git commit -m "feat: skill-to-folder membership, folder filter, folders in detail"
```

---

## Task 5: User page API

**Files:**
- Modify: `backend/users.py`
- Create: `backend/tests/test_user_page.py`

**Interfaces:**
- Consumes: `favorites_of`, `favorite_skill_ids`, `get_permission_level` (services); `Favorite`, `Skill`, `User` (models).
- Produces: `GET /api/users/:id` → `{id, username, display_name, role, created_at, owned_count, favorite_count}`; `GET /api/users/:id/favorites` → list of skill dicts. Both self-or-admin (else 404). Owned skills reuse the existing `GET /api/skills?owner=<id>`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_user_page.py`:

```python
def test_user_page_self_access(client, regular_user, login, make_skill):
    s1 = make_skill(regular_user, "Owned One")
    login(regular_user)
    client.put(f"/api/skills/{s1}/favorite")

    me = client.get(f"/api/users/{regular_user['id']}").get_json()
    assert me["owned_count"] == 1
    assert me["favorite_count"] == 1
    assert me["display_name"] == "Dana"

    favs = client.get(f"/api/users/{regular_user['id']}/favorites").get_json()
    assert [s["id"] for s in favs] == [s1]


def test_admin_can_view_other_user_page(client, admin_user, regular_user, login, make_skill):
    make_skill(regular_user, "Dana Skill")
    login(admin_user)
    resp = client.get(f"/api/users/{regular_user['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["owned_count"] == 1


def test_non_admin_cannot_view_other_user_page(client, regular_user, second_user, login):
    login(regular_user)
    assert client.get(f"/api/users/{second_user['id']}").status_code == 404
    assert client.get(f"/api/users/{second_user['id']}/favorites").status_code == 404


def test_owned_skills_via_owner_filter(client, regular_user, login, make_skill):
    s1 = make_skill(regular_user, "Owner Filter Skill")
    login(regular_user)
    owned = [s["id"] for s in client.get(f"/api/skills?owner={regular_user['id']}").get_json()]
    assert owned == [s1]
```

Note: the `regular_user` fixture creates username `dana` with `display_name="Dana"` (conftest capitalizes the username), so `me["display_name"] == "Dana"`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest backend\tests\test_user_page.py -q`
Expected: FAIL — 404/405 on `/api/users/<id>` (route not defined; only `/api/users` list exists).

- [ ] **Step 3: Add the two endpoints to `users.py`**

In `backend/users.py`, update the models import to add `Favorite`:

```python
from models import PERMISSION_LEVELS, ROLES, Favorite, Skill, SkillPermission, User, db
```

Update the services import to add the helpers:

```python
from services import favorite_skill_ids, favorites_of, get_permission_level, log_action
```

Add these two routes (place them after `list_users`, before `create_user`):

```python
@users_bp.get("/<int:user_id>")
@login_required
def get_user(user_id):
    if not (current_user.is_admin or current_user.id == user_id):
        abort(404, description="User not found")
    user = db.session.get(User, user_id)
    if user is None:
        abort(404, description="User not found")
    data = user.to_dict()
    data["owned_count"] = Skill.query.filter_by(owner_id=user_id).count()
    data["favorite_count"] = Favorite.query.filter_by(user_id=user_id).count()
    return jsonify(data)


@users_bp.get("/<int:user_id>/favorites")
@login_required
def user_favorites(user_id):
    if not (current_user.is_admin or current_user.id == user_id):
        abort(404, description="User not found")
    target = db.session.get(User, user_id)
    if target is None:
        abort(404, description="User not found")
    fav_ids = favorite_skill_ids(current_user)
    skills = favorites_of(target, current_user)
    skills.sort(key=lambda s: s.updated_at, reverse=True)
    return jsonify([
        s.to_dict(
            my_permission=get_permission_level(current_user, s),
            favorited=s.id in fav_ids,
        )
        for s in skills
    ])
```

Note: these use `@login_required` (not `@admin_required`) because the self-or-admin check is inline. Ensure `login_required` is imported (it already is in `users.py`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest backend\tests\test_user_page.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the full backend suite**

Run: `.venv\Scripts\python.exe -m pytest backend\tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/users.py backend/tests/test_user_page.py
git commit -m "feat: user page API (profile, owned counts, favorites)"
```

---

## Task 6: Frontend — FavoriteStar component + SkillDetail wiring

**Files:**
- Create: `frontend/src/components/FavoriteStar.jsx`
- Modify: `frontend/src/pages/SkillDetail.jsx`, `frontend/src/styles.css`

**Interfaces:**
- Consumes: `api` (`frontend/src/api/client.js` — `api.put`, `api.del`); backend `PUT/DELETE /api/skills/:id/favorite` (Task 2).
- Produces: `<FavoriteStar skillId={number} favorited={bool} onChange={(next:bool)=>void} />` — a toggle button that optimistically flips and calls the API.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/FavoriteStar.jsx`:

```jsx
import { useState } from 'react'
import { api } from '../api/client'

export default function FavoriteStar({ skillId, favorited, onChange }) {
  const [on, setOn] = useState(!!favorited)
  const [busy, setBusy] = useState(false)

  const toggle = async (e) => {
    e.stopPropagation()
    e.preventDefault()
    if (busy) return
    setBusy(true)
    const next = !on
    setOn(next) // optimistic
    try {
      if (next) await api.put(`/api/skills/${skillId}/favorite`)
      else await api.del(`/api/skills/${skillId}/favorite`)
      onChange?.(next)
    } catch {
      setOn(!next) // revert on failure
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      type="button"
      className={`fav-star${on ? ' is-on' : ''}`}
      aria-pressed={on}
      aria-label={on ? 'Remove from favorites' : 'Add to favorites'}
      title={on ? 'Remove from favorites' : 'Add to favorites'}
      onClick={toggle}
    >
      {on ? '★' : '☆'}
    </button>
  )
}
```

- [ ] **Step 2: Wire the star into the SkillDetail header**

In `frontend/src/pages/SkillDetail.jsx`, add the import near the other component imports:

```jsx
import FavoriteStar from '../components/FavoriteStar'
```

Then render the star next to the skill title. Find the header area that renders `skill.name` (the `<h1>`/title block near the top of the returned JSX) and place the star beside it, e.g.:

```jsx
<div className="detail-title-row">
  <h1>{skill.name}</h1>
  <FavoriteStar skillId={skill.id} favorited={skill.favorited} />
</div>
```

(If the title is not already wrapped, wrap the existing `<h1>{skill.name}</h1>` and the star together in the `detail-title-row` div shown above — keep the rest of the header untouched.)

- [ ] **Step 3: Add CSS**

Append to `frontend/src/styles.css`:

```css
/* Favorite star */
.fav-star {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.1rem;
  line-height: 1;
  padding: 0 0.15rem;
  color: var(--muted, #8a8f98);
}
.fav-star.is-on { color: #f5c518; }
.fav-star:hover { color: #f5c518; }
.detail-title-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
```

- [ ] **Step 4: Build to verify it compiles**

Run (from `frontend\`): `npm run build`
Expected: build succeeds, no errors.

- [ ] **Step 5: Manual verification**

Start the app: from repo root run `.venv\Scripts\python.exe backend\app.py` (after `cd frontend && npm run build`), open http://localhost:5100, log in as `dana`/`dana123`, open any skill detail page. Click the ☆ — it should fill to ★ and persist across a page refresh. Click again to unset.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/FavoriteStar.jsx frontend/src/pages/SkillDetail.jsx frontend/src/styles.css
git commit -m "feat: favorite star on skill detail"
```

---

## Task 7: Frontend — Dashboard folder sidebar (read-only) + filtering + star column

**Files:**
- Create: `frontend/src/components/FolderTree.jsx`
- Modify: `frontend/src/pages/Dashboard.jsx`, `frontend/src/styles.css`

**Interfaces:**
- Consumes: `api.get('/api/folders')`, `api.get('/api/skills?...&folder=<sel>')`; `FavoriteStar` (Task 6).
- Produces: `<FolderTree folders={list} selected={sel} onSelect={fn} isAdmin={bool} onCreate onRename onDelete onDropSkill />`. In this task only the read-only props (`folders`, `selected`, `onSelect`) are wired; the admin props are consumed in Task 8. `selected` is `null` (All skills), `'unfiled'`, or a numeric folder id.

- [ ] **Step 1: Create the FolderTree component (read-only + inert admin hooks)**

Create `frontend/src/components/FolderTree.jsx`:

```jsx
import { useMemo, useState } from 'react'

// Build a parent_id -> children[] map and render recursively.
function buildTree(folders) {
  const byParent = new Map()
  for (const f of folders) {
    const key = f.parent_id ?? null
    if (!byParent.has(key)) byParent.set(key, [])
    byParent.get(key).push(f)
  }
  return byParent
}

function FolderNode({ folder, byParent, depth, ctx }) {
  const children = byParent.get(folder.id) || []
  const [open, setOpen] = useState(true)
  const isSelected = ctx.selected === folder.id

  const onDrop = (e) => {
    if (!ctx.isAdmin || !ctx.onDropSkill) return
    e.preventDefault()
    const skillId = e.dataTransfer.getData('text/skill-id')
    if (skillId) ctx.onDropSkill(Number(skillId), folder.id)
  }

  return (
    <li>
      <div
        className={`folder-row${isSelected ? ' is-selected' : ''}`}
        style={{ paddingLeft: `${depth * 14 + 8}px` }}
        onClick={() => ctx.onSelect(folder.id)}
        onDragOver={(e) => ctx.isAdmin && e.preventDefault()}
        onDrop={onDrop}
      >
        <button
          type="button"
          className="folder-twisty"
          onClick={(e) => { e.stopPropagation(); setOpen((v) => !v) }}
          aria-label={open ? 'Collapse' : 'Expand'}
        >
          {children.length ? (open ? '▾' : '▸') : '·'}
        </button>
        <span className="folder-name">{folder.name}</span>
        <span className="folder-count">{folder.skill_count}</span>
        {ctx.isAdmin && (
          <span className="folder-actions">
            <button type="button" title="New subfolder"
              onClick={(e) => { e.stopPropagation(); ctx.onCreate(folder.id) }}>＋</button>
            <button type="button" title="Rename"
              onClick={(e) => { e.stopPropagation(); ctx.onRename(folder) }}>✎</button>
            <button type="button" title="Delete"
              onClick={(e) => { e.stopPropagation(); ctx.onDelete(folder) }}>🗑</button>
          </span>
        )}
      </div>
      {open && children.length > 0 && (
        <ul className="folder-children">
          {children.map((c) => (
            <FolderNode key={c.id} folder={c} byParent={byParent} depth={depth + 1} ctx={ctx} />
          ))}
        </ul>
      )}
    </li>
  )
}

export default function FolderTree({
  folders, selected, onSelect,
  isAdmin = false, onCreate, onRename, onDelete, onDropSkill,
}) {
  const byParent = useMemo(() => buildTree(folders || []), [folders])
  const roots = byParent.get(null) || []
  const ctx = { selected, onSelect, isAdmin, onCreate, onRename, onDelete, onDropSkill }

  return (
    <aside className="folder-sidebar">
      <div className="folder-sidebar-head">
        <span>Folders</span>
        {isAdmin && (
          <button type="button" className="btn btn-ghost btn-sm"
            onClick={() => onCreate(null)}>+ New</button>
        )}
      </div>
      <ul className="folder-tree">
        <li>
          <div className={`folder-row${selected === null ? ' is-selected' : ''}`}
            style={{ paddingLeft: '8px' }} onClick={() => onSelect(null)}>
            <span className="folder-twisty">★</span>
            <span className="folder-name">All skills</span>
          </div>
        </li>
        <li>
          <div className={`folder-row${selected === 'unfiled' ? ' is-selected' : ''}`}
            style={{ paddingLeft: '8px' }} onClick={() => onSelect('unfiled')}>
            <span className="folder-twisty">⌫</span>
            <span className="folder-name">Unfiled</span>
          </div>
        </li>
        {roots.map((f) => (
          <FolderNode key={f.id} folder={f} byParent={byParent} depth={0} ctx={ctx} />
        ))}
      </ul>
    </aside>
  )
}
```

- [ ] **Step 2: Rewrite `Dashboard.jsx` to add the sidebar, folder filter, and star column**

Replace the entire contents of `frontend/src/pages/Dashboard.jsx` with:

```jsx
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import StatusBadge from '../components/StatusBadge'
import TagChips from '../components/TagChips'
import SkillFormModal from '../components/SkillFormModal'
import FavoriteStar from '../components/FavoriteStar'
import FolderTree from '../components/FolderTree'

export default function Dashboard() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [allSkills, setAllSkills] = useState(null) // unfiltered, for options
  const [skills, setSkills] = useState(null)
  const [folders, setFolders] = useState([])
  const [selectedFolder, setSelectedFolder] = useState(null) // null | 'unfiled' | id
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const [search, setSearch] = useState('')
  const [q, setQ] = useState('') // debounced
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [owner, setOwner] = useState('')
  const [tag, setTag] = useState('')

  const loadFolders = () =>
    api.get('/api/folders').then(setFolders).catch(() => setFolders([]))

  useEffect(() => {
    api.get('/api/skills').then(setAllSkills).catch((e) => setError(e.message))
    loadFolders()
  }, [])

  useEffect(() => {
    const t = setTimeout(() => setQ(search), 300)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (status) params.set('status', status)
    if (category) params.set('category', category)
    if (owner) params.set('owner', owner)
    if (tag) params.set('tag', tag)
    if (selectedFolder === 'unfiled') params.set('folder', 'unfiled')
    else if (selectedFolder != null) params.set('folder', String(selectedFolder))
    api
      .get(`/api/skills?${params.toString()}`)
      .then(setSkills)
      .catch((e) => setError(e.message))
  }, [q, status, category, owner, tag, selectedFolder])

  const options = useMemo(() => {
    const categories = new Set()
    const owners = new Set()
    for (const s of allSkills || []) {
      if (s.category) categories.add(s.category)
      owners.add(s.owner.display_name)
    }
    return {
      categories: [...categories].sort(),
      owners: [...owners].sort(),
    }
  }, [allSkills])

  const createSkill = async (payload) => {
    const skill = await api.post('/api/skills', payload)
    navigate(`/skills/${skill.id}`)
  }

  return (
    <div className="dashboard-layout">
      <FolderTree
        folders={folders}
        selected={selectedFolder}
        onSelect={setSelectedFolder}
        isAdmin={false}
      />

      <div className="dashboard-main">
        <div className="page-header">
          <div>
            <h1>Skills</h1>
            <div className="subtitle">
              {skills ? `${skills.length} skill${skills.length === 1 ? '' : 's'} visible to you` : ' '}
            </div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + New Skill
          </button>
        </div>

        {error && <div className="banner banner-error">{error}</div>}

        <div className="card">
          <div className="toolbar">
            <input
              type="search"
              placeholder="Search name or description…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              <option value="draft">draft</option>
              <option value="active">active</option>
              <option value="deprecated">deprecated</option>
            </select>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {options.categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select value={owner} onChange={(e) => setOwner(e.target.value)}>
              <option value="">All owners</option>
              {options.owners.map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
            {tag && (
              <span className="chip selected clickable" onClick={() => setTag('')}>
                tag: {tag} ✕
              </span>
            )}
          </div>

          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th aria-label="Favorite"></th>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Category</th>
                  <th>Tags</th>
                  <th>Owner</th>
                  <th>Status</th>
                  <th>Ver</th>
                  <th>Access</th>
                </tr>
              </thead>
              <tbody>
                {(skills || []).map((s) => (
                  <tr key={s.id}>
                    <td>
                      <FavoriteStar skillId={s.id} favorited={s.favorited} />
                    </td>
                    <td className="cell-name">
                      <Link to={`/skills/${s.id}`}>{s.name}</Link>
                    </td>
                    <td className="cell-muted">
                      {s.description.length > 70
                        ? s.description.slice(0, 70) + '…'
                        : s.description}
                    </td>
                    <td className="cell-muted">{s.category}</td>
                    <td>
                      <TagChips tags={s.tags} selected={tag} onTagClick={setTag} />
                    </td>
                    <td className="cell-muted">
                      <Link to={`/users/${s.owner.id}`}>{s.owner.display_name}</Link>
                    </td>
                    <td>
                      <StatusBadge status={s.status} />
                    </td>
                    <td>
                      <span className="mono">v{s.current_version}</span>
                    </td>
                    <td>
                      <span className="badge badge-perm">{s.my_permission}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {skills && skills.length === 0 && (
              <div className="empty-state">No skills match the current filters.</div>
            )}
          </div>
        </div>
      </div>

      {showCreate && (
        <SkillFormModal
          title="New Skill"
          submitLabel="Create"
          uploadOption
          onUploaded={(skill) => navigate(`/skills/${skill.id}`)}
          onSubmit={createSkill}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  )
}
```

Note: the owner cell now links to `/users/:id` (Task 9 adds the page; the link is harmless until then). `useAuth` is imported now for use in Task 8.

- [ ] **Step 3: Add CSS for the layout and tree**

Append to `frontend/src/styles.css`:

```css
/* Dashboard + folder sidebar layout */
.dashboard-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 1rem;
  align-items: start;
}
.dashboard-main { min-width: 0; }
@media (max-width: 720px) {
  .dashboard-layout { grid-template-columns: 1fr; }
}

.folder-sidebar {
  border: 1px solid var(--border, #2a2f3a);
  border-radius: 8px;
  padding: 0.5rem;
  font-size: 0.9rem;
  position: sticky;
  top: 1rem;
}
.folder-sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  padding: 0.25rem 0.4rem 0.5rem;
}
.folder-tree, .folder-children { list-style: none; margin: 0; padding: 0; }
.folder-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.4rem;
  border-radius: 6px;
  cursor: pointer;
}
.folder-row:hover { background: var(--hover, #1c2130); }
.folder-row.is-selected { background: var(--accent-muted, #24304a); }
.folder-twisty {
  background: none; border: none; color: inherit; cursor: pointer;
  width: 1.1em; text-align: center; padding: 0;
}
.folder-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.folder-count { color: var(--muted, #8a8f98); font-size: 0.8rem; }
.folder-actions { display: none; gap: 0.15rem; }
.folder-row:hover .folder-actions { display: inline-flex; }
.folder-actions button {
  background: none; border: none; cursor: pointer; padding: 0 0.15rem;
  color: var(--muted, #8a8f98);
}
.btn-sm { padding: 0.15rem 0.5rem; font-size: 0.8rem; }
```

- [ ] **Step 4: Build to verify it compiles**

Run (from `frontend\`): `npm run build`
Expected: build succeeds.

- [ ] **Step 5: Manual verification**

Rebuild + run the app. Log in as `dana`. Confirm: the folder sidebar renders with "All skills" and "Unfiled". Since no folders exist yet, only those two show. Each table row has a star column, and owner names are links. Selecting "Unfiled" shows all skills (none are filed yet); "All skills" shows the full list. (Create folders comes in Task 8.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/FolderTree.jsx frontend/src/pages/Dashboard.jsx frontend/src/styles.css
git commit -m "feat: dashboard folder sidebar, folder filter, favorite column"
```

---

## Task 8: Frontend — Folder admin controls (create/rename/delete, drag-move, Folders menu, bulk move)

**Files:**
- Create: `frontend/src/components/FolderMenu.jsx`
- Modify: `frontend/src/pages/Dashboard.jsx`, `frontend/src/styles.css`

**Interfaces:**
- Consumes: `FolderTree` admin props (Task 7); `api.post/put/del`; backend `POST/PUT/DELETE /api/folders`, `POST /api/folders/:id/skills`, `PUT /api/skills/:id/folders`.
- Produces: `<FolderMenu skillId currentFolderIds folders onApply />` (checkbox popover setting exact membership); Dashboard gains admin handlers, row drag, per-row Folders button, bulk-select + Move-to bar.

- [ ] **Step 1: Create the FolderMenu popover**

Create `frontend/src/components/FolderMenu.jsx`:

```jsx
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

// A checkbox popover: check/uncheck folders to set a skill's exact membership.
export default function FolderMenu({ skillId, currentFolderIds, folders, onApply, onClose }) {
  const [checked, setChecked] = useState(new Set(currentFolderIds || []))
  const [busy, setBusy] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose?.() }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [onClose])

  const toggle = (id) => {
    setChecked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const apply = async () => {
    setBusy(true)
    try {
      const folderIds = [...checked]
      await api.put(`/api/skills/${skillId}/folders`, { folder_ids: folderIds })
      onApply?.(folderIds)
      onClose?.()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="folder-menu" ref={ref}>
      <div className="folder-menu-title">Folders</div>
      <div className="folder-menu-list">
        {folders.length === 0 && <div className="cell-muted">No folders yet.</div>}
        {folders.map((f) => (
          <label key={f.id} className="folder-menu-item">
            <input type="checkbox" checked={checked.has(f.id)} onChange={() => toggle(f.id)} />
            {f.name}
          </label>
        ))}
      </div>
      <div className="folder-menu-actions">
        <button className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>Cancel</button>
        <button className="btn btn-primary btn-sm" onClick={apply} disabled={busy}>Apply</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add admin state + handlers to `Dashboard.jsx`**

In `frontend/src/pages/Dashboard.jsx`, add the import:

```jsx
import FolderMenu from '../components/FolderMenu'
```

Add `const isAdmin = user?.role === 'admin'` near the top of the component (after `const { user } = useAuth()`), and add this admin state below the existing `useState` hooks:

```jsx
  const [selectedIds, setSelectedIds] = useState(new Set()) // bulk-select skill ids
  const [menuFor, setMenuFor] = useState(null)              // skillId with open FolderMenu
  const [skillFolderIds, setSkillFolderIds] = useState({})  // skillId -> [folderId] cache
```

Add these handlers inside the component (above the `return`):

```jsx
  const reload = () => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (status) params.set('status', status)
    if (category) params.set('category', category)
    if (owner) params.set('owner', owner)
    if (tag) params.set('tag', tag)
    if (selectedFolder === 'unfiled') params.set('folder', 'unfiled')
    else if (selectedFolder != null) params.set('folder', String(selectedFolder))
    api.get(`/api/skills?${params.toString()}`).then(setSkills).catch((e) => setError(e.message))
  }

  const createFolder = async (parentId) => {
    const name = window.prompt('New folder name:')
    if (!name || !name.trim()) return
    try {
      await api.post('/api/folders', { name: name.trim(), parent_id: parentId })
      loadFolders()
    } catch (e) { setError(e.message) }
  }

  const renameFolder = async (folder) => {
    const name = window.prompt('Rename folder:', folder.name)
    if (!name || !name.trim() || name.trim() === folder.name) return
    try {
      await api.put(`/api/folders/${folder.id}`, { name: name.trim() })
      loadFolders()
    } catch (e) { setError(e.message) }
  }

  const deleteFolder = async (folder) => {
    if (!window.confirm(
      `Delete "${folder.name}"? Subfolders are deleted and their skills become unfiled. Skills are not deleted.`
    )) return
    try {
      await api.del(`/api/folders/${folder.id}`)
      if (selectedFolder === folder.id) setSelectedFolder(null)
      loadFolders()
      reload()
    } catch (e) { setError(e.message) }
  }

  const dropSkillOnFolder = async (skillId, folderId) => {
    try {
      // drag = move: membership becomes exactly [folderId]
      await api.put(`/api/skills/${skillId}/folders`, { folder_ids: [folderId] })
      loadFolders()
      reload()
    } catch (e) { setError(e.message) }
  }

  const toggleSelected = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const bulkMoveTo = async (folderId) => {
    if (!selectedIds.size) return
    try {
      await api.post(`/api/folders/${folderId}/skills`, {
        skill_ids: [...selectedIds], mode: 'move',
      })
      setSelectedIds(new Set())
      loadFolders()
      reload()
    } catch (e) { setError(e.message) }
  }

  const openFolderMenu = async (skillId) => {
    if (menuFor === skillId) { setMenuFor(null); return }
    try {
      const detail = await api.get(`/api/skills/${skillId}`)
      setSkillFolderIds((m) => ({ ...m, [skillId]: (detail.folders || []).map((f) => f.id) }))
      setMenuFor(skillId)
    } catch (e) { setError(e.message) }
  }
```

- [ ] **Step 3: Pass admin props to FolderTree**

In `Dashboard.jsx`, replace the `<FolderTree ... isAdmin={false} />` element with:

```jsx
      <FolderTree
        folders={folders}
        selected={selectedFolder}
        onSelect={setSelectedFolder}
        isAdmin={isAdmin}
        onCreate={createFolder}
        onRename={renameFolder}
        onDelete={deleteFolder}
        onDropSkill={dropSkillOnFolder}
      />
```

- [ ] **Step 4: Add the bulk-move bar (admin only)**

In `Dashboard.jsx`, immediately after the `{error && ...}` banner line and before `<div className="card">`, add:

```jsx
        {isAdmin && selectedIds.size > 0 && (
          <div className="bulk-bar">
            <span>{selectedIds.size} selected</span>
            <label>
              Move to:
              <select
                defaultValue=""
                onChange={(e) => { if (e.target.value) bulkMoveTo(Number(e.target.value)) }}
              >
                <option value="" disabled>Choose folder…</option>
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </label>
            <button className="btn btn-ghost btn-sm" onClick={() => setSelectedIds(new Set())}>
              Clear
            </button>
          </div>
        )}
```

- [ ] **Step 5: Add the admin controls to each table row**

In `Dashboard.jsx`, add a bulk-select checkbox header. In the `<thead>` row, change the first header cell:

```jsx
                  <th aria-label="Select">
                    {isAdmin ? <span className="cell-muted">☑</span> : ''}
                  </th>
```

In each row `<tr>`, replace the first `<td>` (the FavoriteStar cell) with a cell that holds both the admin checkbox and the star, and make the row draggable for admins:

```jsx
                  <tr
                    key={s.id}
                    draggable={isAdmin}
                    onDragStart={(e) => e.dataTransfer.setData('text/skill-id', String(s.id))}
                  >
                    <td className="cell-select">
                      {isAdmin && (
                        <input
                          type="checkbox"
                          checked={selectedIds.has(s.id)}
                          onChange={() => toggleSelected(s.id)}
                        />
                      )}
                      <FavoriteStar skillId={s.id} favorited={s.favorited} />
                    </td>
```

Then add a per-row "Folders…" control for admins. In the same row, change the Access `<td>` to include a Folders button + popover:

```jsx
                    <td className="cell-access">
                      <span className="badge badge-perm">{s.my_permission}</span>
                      {isAdmin && (
                        <span className="folder-menu-anchor">
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => openFolderMenu(s.id)}
                          >
                            Folders…
                          </button>
                          {menuFor === s.id && (
                            <FolderMenu
                              skillId={s.id}
                              currentFolderIds={skillFolderIds[s.id] || []}
                              folders={folders}
                              onClose={() => setMenuFor(null)}
                              onApply={() => { loadFolders(); reload() }}
                            />
                          )}
                        </span>
                      )}
                    </td>
```

- [ ] **Step 6: Add CSS**

Append to `frontend/src/styles.css`:

```css
/* Bulk move bar */
.bulk-bar {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.5rem 0.75rem; margin-bottom: 0.5rem;
  border: 1px solid var(--accent-muted, #24304a); border-radius: 8px;
}
.cell-select { display: flex; align-items: center; gap: 0.35rem; white-space: nowrap; }
.cell-access { position: relative; white-space: nowrap; }
.folder-menu-anchor { position: relative; }

/* Folder membership popover */
.folder-menu {
  position: absolute; right: 0; top: 100%; z-index: 30;
  min-width: 200px; margin-top: 4px; padding: 0.5rem;
  background: var(--panel, #141824); border: 1px solid var(--border, #2a2f3a);
  border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.35);
}
.folder-menu-title { font-weight: 600; margin-bottom: 0.4rem; }
.folder-menu-list { max-height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.25rem; }
.folder-menu-item { display: flex; align-items: center; gap: 0.4rem; cursor: pointer; }
.folder-menu-actions { display: flex; justify-content: flex-end; gap: 0.4rem; margin-top: 0.5rem; }
tr[draggable='true'] { cursor: grab; }
```

- [ ] **Step 7: Build to verify it compiles**

Run (from `frontend\`): `npm run build`
Expected: build succeeds.

- [ ] **Step 8: Manual verification**

Rebuild + run. Log in as `admin`/`admin123`:
1. Click "+ New" in the sidebar → create "Backend". Hover it → use ＋ to add a subfolder "Auth". Rename and delete work via ✎/🗑.
2. Drag a skill row onto "Backend" → it moves there (count increments; selecting Backend shows it; it disappears from other folders).
3. Click "Folders…" on a row → check multiple folders → Apply → selecting each shows the skill (multi-membership).
4. Tick several row checkboxes → the bulk bar appears → pick a folder in "Move to" → the skills move.
Log in as `dana` (non-admin): the tree shows with counts but no ＋/✎/🗑, no drag, no checkboxes, no "Folders…" button.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/FolderMenu.jsx frontend/src/pages/Dashboard.jsx frontend/src/styles.css
git commit -m "feat: admin folder management, drag-move, folders menu, bulk move"
```

---

## Task 9: Frontend — User page + route + nav link

**Files:**
- Create: `frontend/src/pages/UserPage.jsx`
- Modify: `frontend/src/App.jsx`, `frontend/src/pages/SkillDetail.jsx`, `frontend/src/styles.css`

**Interfaces:**
- Consumes: `api.get('/api/users/:id')`, `api.get('/api/users/:id/favorites')`, `api.get('/api/skills?owner=:id')`; `FavoriteStar`, `StatusBadge`.
- Produces: route `/users/:id` rendering profile + "Skills I own" + "Favorites"; a "My Page" nav link; owner links on SkillDetail.

- [ ] **Step 1: Create the UserPage**

Create `frontend/src/pages/UserPage.jsx`:

```jsx
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import FavoriteStar from '../components/FavoriteStar'

function SkillTable({ rows, emptyText }) {
  if (!rows) return <div className="page-loading">Loading…</div>
  if (rows.length === 0) return <div className="empty-state">{emptyText}</div>
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th aria-label="Favorite"></th>
            <th>Name</th>
            <th>Category</th>
            <th>Status</th>
            <th>Ver</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td><FavoriteStar skillId={s.id} favorited={s.favorited} /></td>
              <td className="cell-name"><Link to={`/skills/${s.id}`}>{s.name}</Link></td>
              <td className="cell-muted">{s.category}</td>
              <td><StatusBadge status={s.status} /></td>
              <td><span className="mono">v{s.current_version}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function UserPage() {
  const { id } = useParams()
  const [profile, setProfile] = useState(null)
  const [owned, setOwned] = useState(null)
  const [favorites, setFavorites] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setProfile(null); setOwned(null); setFavorites(null); setError(null)
    api.get(`/api/users/${id}`).then(setProfile).catch((e) => setError(e.message))
    api.get(`/api/skills?owner=${id}`).then(setOwned).catch(() => setOwned([]))
    api.get(`/api/users/${id}/favorites`).then(setFavorites).catch(() => setFavorites([]))
  }, [id])

  if (error) {
    return <div className="empty-state">User not found (or you have no access).</div>
  }
  if (!profile) return <div className="page-loading">Loading…</div>

  return (
    <div className="user-page">
      <div className="page-header">
        <div>
          <h1>{profile.display_name}</h1>
          <div className="subtitle">
            <span className="badge badge-perm">{profile.role}</span>{' '}
            @{profile.username} · joined {new Date(profile.created_at).toLocaleDateString()} ·{' '}
            {profile.owned_count} owned · {profile.favorite_count} favorites
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="section-title">Skills owned</h2>
        <SkillTable rows={owned} emptyText="No skills owned yet." />
      </div>

      <div className="card">
        <h2 className="section-title">Favorites</h2>
        <SkillTable rows={favorites} emptyText="No favorites yet." />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add the route + nav link in `App.jsx`**

In `frontend/src/App.jsx`, add the import:

```jsx
import UserPage from './pages/UserPage'
```

Add the route inside the authenticated `<Route path="/" ...>` block, next to the other child routes:

```jsx
        <Route path="users/:id" element={<UserPage />} />
```

Add a "My Page" nav link. In the `<nav className="nav-links">` block, after the Dashboard/Graph links, add:

```jsx
          <NavLink to={`/users/${user?.id}`}>My Page</NavLink>
```

- [ ] **Step 3: Link the owner name on SkillDetail**

In `frontend/src/pages/SkillDetail.jsx`, ensure `Link` is imported from `react-router-dom` (it imports `useNavigate, useParams` already — add `Link`):

```jsx
import { Link, useNavigate, useParams } from 'react-router-dom'
```

Wherever the owner is displayed (`skill.owner.display_name`), wrap it in a link:

```jsx
<Link to={`/users/${skill.owner.id}`}>{skill.owner.display_name}</Link>
```

(If SkillDetail does not currently show the owner, skip this sub-step — the Dashboard owner link from Task 7 already covers navigation. Do not add a new owner field if one isn't present.)

- [ ] **Step 4: Add CSS**

Append to `frontend/src/styles.css`:

```css
.user-page .card { margin-bottom: 1rem; }
.section-title { margin: 0 0 0.5rem; font-size: 1rem; }
```

- [ ] **Step 5: Build to verify it compiles**

Run (from `frontend\`): `npm run build`
Expected: build succeeds.

- [ ] **Step 6: Manual verification**

Rebuild + run. Log in as `dana`:
1. Click "My Page" → see Dana's profile, "Skills owned" (Jira Ticket Triage, Meeting Prep Assistant), and "Favorites" (whatever you starred).
2. From the Dashboard, click an owner name → navigate to that user's page.
3. As `dana`, manually visiting `/users/<yossi-id>` should show "User not found" (non-admin). Log in as `admin` and visit `/users/<dana-id>` → it loads (admin oversight).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/UserPage.jsx frontend/src/App.jsx frontend/src/pages/SkillDetail.jsx frontend/src/styles.css
git commit -m "feat: user page with owned skills and favorites"
```

---

## Task 10: (Optional) Seed demo folders + favorites

**Files:**
- Modify: `backend/seed.py`

**Interfaces:**
- Consumes: `Folder`, `SkillFolder`, `Favorite` (models); the `users`/`skills` dicts built in `seed.py`.
- Produces: a small demo folder tree, memberships, and a few favorites so the features are visible immediately after `seed.py --force`.

- [ ] **Step 1: Add seed data structures and a builder**

In `backend/seed.py`, update the models import:

```python
from models import (
    Favorite, Folder, SkillFolder, SkillPermission, SkillRelationship, User, db,
)
```

After the `PERMISSIONS` list, add:

```python
# (folder key, display name, parent key or None)
FOLDERS = [
    ("processing", "Document Processing", None),
    ("extraction", "Data Extraction", None),
    ("quality", "Quality & Reporting", None),
    ("quality_coc", "COC", "quality"),
]

# (folder key, skill key) memberships
FOLDER_SKILLS = [
    ("processing", "summarizer"),
    ("processing", "regulation"),
    ("extraction", "pdf_tables"),
    ("extraction", "stability"),
    ("quality", "coc_report"),
    ("quality_coc", "coc_report"),   # multi-folder membership demo
]

# (username, skill key) favorites
FAVORITES = [
    ("dana", "summarizer"),
    ("dana", "meeting_prep"),
    ("yossi", "pdf_tables"),
]


def make_folders(users, skills):
    folders = {}
    for key, name, parent_key in FOLDERS:
        parent_id = folders[parent_key].id if parent_key else None
        folder = Folder(name=name, parent_id=parent_id, created_by=users["admin"].id)
        db.session.add(folder)
        db.session.flush()  # assign id for children/memberships
        folders[key] = folder
    for folder_key, skill_key in FOLDER_SKILLS:
        db.session.add(SkillFolder(
            skill_id=skills[skill_key].id, folder_id=folders[folder_key].id,
        ))
    db.session.commit()
    return folders


def make_favorites(users, skills):
    for username, skill_key in FAVORITES:
        db.session.add(Favorite(
            user_id=users[username].id, skill_id=skills[skill_key].id,
        ))
    db.session.commit()
```

- [ ] **Step 2: Call the builders in `main`**

In `backend/seed.py`, inside `main`'s `with app.app_context():` block, after `make_permissions(users, skills)`, add:

```python
        make_folders(users, skills)
        make_favorites(users, skills)
```

And update the summary print to mention them:

```python
        print(f"Seeded {len(users)} users, {len(skills)} skills, "
              f"{len(RELATIONSHIPS)} relationships, {len(PERMISSIONS)} permissions, "
              f"{len(FOLDERS)} folders, {len(FAVORITES)} favorites.")
```

- [ ] **Step 3: Reseed and verify**

Run: `.venv\Scripts\python.exe backend\seed.py --force`
Expected: prints the summary line including folders and favorites, no errors.

- [ ] **Step 4: Run the full backend suite (unaffected)**

Run: `.venv\Scripts\python.exe -m pytest backend\tests -q`
Expected: all pass (tests use an in-memory DB and don't run seed).

- [ ] **Step 5: Manual verification**

Run the app, log in as `admin` → the sidebar shows "Document Processing", "Data Extraction", "Quality & Reporting" (with a "COC" subfolder). Selecting each shows its skills; "COC Report Generator" appears in both "Quality & Reporting" and "COC". Log in as `dana` → "My Page" shows the two seeded favorites.

- [ ] **Step 6: Commit**

```bash
git add backend/seed.py
git commit -m "chore: seed demo folders and favorites"
```

---

## Self-Review (completed by plan author)

**Spec coverage:**
- User page (owned + favorites, self/admin) → Task 5 (API) + Task 9 (UI). ✓
- Favorites private, star on dashboard + detail → Task 2 (API) + Task 6 (detail star) + Task 7 (dashboard column). ✓
- Global admin-managed folder tree, subfolders → Task 3 (CRUD) + Task 7/8 (UI). ✓
- Multi-folder membership + drag = move + Folders menu + bulk → Task 4 (API) + Task 8 (UI). ✓
- Clicking folder shows direct skills only, visibility-filtered → Task 4 (`folder` filter uses `visible_skills`) + Task 7 (select→param). ✓
- Everyone sees the tree, mutations admin-only → Task 3 (`require_admin` on mutations, open GET) + Task 7/8 (isAdmin gating). ✓
- Cascades (skill/folder/user delete) → Task 1 + test coverage. ✓
- Edge cases (cycle, duplicate sibling, favorite-then-lose-access) → Tasks 3/4 tests, Task 2 test. ✓
- Seed demo data (nice-to-have) → Task 10. ✓

**Placeholder scan:** No "TBD"/"handle appropriately"/"write tests for the above" — every code and test step contains concrete content. The only conditional is Task 9 Step 3 (owner field may not exist on SkillDetail), which gives an explicit skip instruction. ✓

**Type/name consistency:** `require_admin`, `favorite_skill_ids`, `toggle_favorite`, `visible_favorites`, `favorites_of`, `get_folder_or_404`, `create_folder`, `update_folder`, `delete_folder`, `visible_folder_tree`, `set_skill_folders`, `bulk_assign`, `skill_folders` are defined once (Tasks 2-4) and consumed with matching signatures in later tasks. `Skill.to_dict(my_permission, favorited)` is defined in Task 1 and called consistently. Frontend `FolderTree`/`FolderMenu`/`FavoriteStar` prop names match between definition and use. `folder_ids` / `skill_ids` / `mode` request keys match between endpoints and callers. ✓
