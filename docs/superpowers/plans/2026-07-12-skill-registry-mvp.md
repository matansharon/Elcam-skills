# Skill Registry MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Elcam Skill Registry MVP — a Flask + React + SQLite web app for versioned organizational AI skills with RBAC, typed relationships, and an interactive graph.

**Architecture:** Flask REST API (`backend/`, app-factory + blueprints, SQLAlchemy on SQLite, session-cookie auth via Flask-Login) and a React + Vite SPA (`frontend/`) talking to `/api/*`. Vite dev-proxies to Flask; for demo Flask serves `frontend/dist`. Permission checks live in a service layer; graph endpoint returns generic `{nodes, edges}` JSON.

**Tech Stack:** Python 3.10, Flask, Flask-Login, Flask-SQLAlchemy, pytest; React 18, Vite, react-router-dom, cytoscape, diff (jsdiff), react-markdown.

**Spec:** `docs/superpowers/specs/2026-07-12-skill-registry-design.md`

## Global Constraints

- Use `python` (never `python3`) — Windows machine; interpreter at `C:\Users\Matan\AppData\Local\Programs\Python\Python310\python.exe`.
- Create a project-local venv at `.venv` before any pip usage; use `.venv\Scripts\python.exe -m pip ...`.
- All commits: no AI attribution lines of any kind.
- UI text: English only.
- Ports: Flask 5000, Vite dev 5173.
- API errors: JSON `{"error": "<message>"}` with status 400/401/403/404. Non-admins get 404 (not 403) for skills they cannot see.
- Statuses: `draft|active|deprecated`. Permission levels: `read|edit`. Relationship types: `depends_on|extends|used_with|replaces`. Roles: `admin|user`.

---

### Task 1: Backend scaffold, models, app factory

**Files:**
- Create: `.gitignore`, `backend/requirements.txt`, `backend/config.py`, `backend/models.py`, `backend/app.py`, `backend/tests/conftest.py`, `backend/tests/test_smoke.py`

**Interfaces:**
- Produces: `create_app(config_object=None)` in `backend/app.py`; models `User, Skill, SkillVersion, SkillPermission, SkillRelationship, AuditLog` and `db` in `backend/models.py`; pytest fixtures `app`, `client` in conftest.
- Model fields exactly as spec §4. `User.set_password(pw)` / `User.check_password(pw)` (werkzeug). `Skill.tags` and `SkillVersion.tags` are `db.JSON`. `to_dict()` on every model returning the API JSON shapes (spec §5): skill dict includes `owner: {id, display_name}`, `current_version` (max version_number), and accepts optional `my_permission` param.

**Steps:**

- [ ] Create `.venv` (`python -m venv .venv`), write `requirements.txt` (flask, flask-sqlalchemy, flask-login, pytest), install.
- [ ] Write failing `backend/tests/test_smoke.py`: `create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})` starts; `GET /api/health` → 200 `{"status": "ok"}`; all six models create tables without error and a User round-trips password hashing.
- [ ] Run `pytest backend/tests -v` → FAIL (module missing).
- [ ] Implement `models.py` (all six models per spec §4 with uniques/cascades: deleting Skill cascades versions/permissions/relationships/audit), `config.py` (dev config: `sqlite:///<abs path>/skills.db`, `SECRET_KEY`), `app.py` (`create_app`: init db + LoginManager, register blueprints later, `/api/health` route, JSON error handlers for 400/401/403/404 returning `{"error": ...}`).
- [ ] `pytest backend/tests -v` → PASS. Commit `feat: backend scaffold with models and app factory`.

### Task 2: Auth blueprint

**Files:**
- Create: `backend/auth.py`, `backend/tests/test_auth.py`
- Modify: `backend/app.py` (register blueprint), `backend/tests/conftest.py` (add `admin_user`, `regular_user` fixtures + `login(client, username, password)` helper)

**Interfaces:**
- Produces: `POST /api/auth/login {username, password}` → 200 user dict / 401; `POST /api/auth/logout` → 200; `GET /api/auth/me` → 200 user dict or 401. Flask-Login `login_required` protects everything except login/health. `user_loader` set up. Unauthorized handler returns JSON 401 (not redirect).

**Steps:**

- [ ] Failing tests: login ok → user json with role; wrong password → 401; `me` unauthenticated → 401 JSON; `me` after login → user; after logout → 401.
- [ ] Run → FAIL. Implement `auth.py` blueprint + wire into `create_app`.
- [ ] Run → PASS. Commit `feat: session auth with Flask-Login`.

### Task 3: Permission service + skills CRUD with versioning

**Files:**
- Create: `backend/services.py`, `backend/skills.py`, `backend/tests/test_skills.py`
- Modify: `backend/app.py`, `backend/tests/conftest.py` (fixture `make_skill(owner, **kw)`)

**Interfaces:**
- Produces in `services.py`:
  - `get_permission_level(user, skill) -> 'edit' | 'read' | None` (admin→edit, owner→edit, else SkillPermission row, else None)
  - `visible_skills(user) -> list[Skill]` (admin: all; else owned + permitted)
  - `create_skill(user, data) -> Skill` — creates Skill + SkillVersion #1 + audit `create`
  - `update_skill(user, skill, data) -> SkillVersion` — updates Skill current fields, snapshot version N+1 with `change_note`, audit `update`
  - `restore_version(user, skill, n) -> SkillVersion` — copies snapshot n into version N+1, note `Restored from version n`, audit `restore`
  - `log_action(skill_id, user_id, action, detail)`
- Produces routes: `GET /api/skills` (filters `q, tag, category, owner, status`; each dict includes `my_permission`), `POST /api/skills` (any authed user; becomes owner; `name` required + unique → 400), `GET/PUT/DELETE /api/skills/<id>` (read/edit/owner-or-admin respectively; invisible → 404).

**Steps:**

- [ ] Failing tests covering: owner CRUD; version 1 created on create; PUT bumps version and updates fields; user with no permission gets 404 on GET/PUT and skill absent from list; `read` user can GET but PUT → 403; `edit` user can PUT but DELETE → 403 (owner/admin only); admin sees all; filters `q`/`tag`/`status` work; duplicate name → 400.
- [ ] Run → FAIL. Implement `services.py` + `skills.py`.
- [ ] Run → PASS. Commit `feat: skills CRUD with RBAC and automatic versioning`.

### Task 4: Version history, restore, audit endpoints

**Files:**
- Create: `backend/tests/test_versions.py`
- Modify: `backend/skills.py`

**Interfaces:**
- Produces: `GET /api/skills/<id>/versions` (desc order, read); `GET /api/skills/<id>/versions/<n>` (read, 404 unknown n); `POST /api/skills/<id>/versions/<n>/restore` (edit) → new version dict; `GET /api/skills/<id>/audit` (read) → `[{action, detail, user: display_name, created_at}]` desc.

**Steps:**

- [ ] Failing tests: after create + 2 updates → 3 versions desc; version content snapshots differ; restore v1 → creates v4 whose content equals v1's and skill current fields updated; old versions untouched; read-only user can list versions but restore → 403; audit contains create/update/restore rows.
- [ ] Run → FAIL. Implement routes.
- [ ] Run → PASS. Commit `feat: version history, restore, and audit trail`.

### Task 5: Relationships + graph endpoint

**Files:**
- Create: `backend/relationships.py`, `backend/tests/test_relationships.py`
- Modify: `backend/app.py`

**Interfaces:**
- Produces: `POST /api/relationships {source_skill_id, target_skill_id, type}` (needs edit on source; both visible; self-link → 400; dup (s,t,type) → 400; bad type → 400; audit `relationship_added` on source skill); `DELETE /api/relationships/<id>` (edit on source; audit `relationship_removed`); `GET /api/skills/<id>/links` → `{outgoing: [{id, type, skill: {id, name, status}}], incoming: [...]}` filtered to visible endpoints; `GET /api/graph` → `{nodes: [{id, name, category, tags, status}], edges: [{id, source, target, type}]}` — only skills the caller can read, edges only when both endpoints visible.

**Steps:**

- [ ] Failing tests: create/delete; self-link, duplicate, invalid type → 400; read-only on source → 403; links shows both directions; graph for restricted user omits invisible nodes and their edges; admin graph complete.
- [ ] Run → FAIL. Implement.
- [ ] Run → PASS. Commit `feat: typed skill relationships and graph endpoint`.

### Task 6: Admin users & permissions management

**Files:**
- Create: `backend/users.py`, `backend/tests/test_users.py`
- Modify: `backend/app.py`

**Interfaces:**
- Produces (all admin-only → else 403): `GET /api/users`; `POST /api/users {username, password, display_name, role}` (dup username → 400); `DELETE /api/users/<id>` (cannot delete self → 400; owned skills' `owner_id` reassigned to acting admin; permissions rows deleted); `GET /api/users/<id>/permissions` → `[{skill_id, skill_name, level}]`; `PUT /api/users/<id>/permissions/<skill_id> {level: 'read'|'edit'|null}` (null removes; upsert; audit `permission_set`/`permission_removed` on the skill).

**Steps:**

- [ ] Failing tests: non-admin → 403 on every route; create/list/delete user; self-delete → 400; permission upsert changes what target user sees (skill appears/disappears in their `/api/skills`); remove permission.
- [ ] Run → FAIL. Implement `users.py`.
- [ ] Run → PASS. Commit `feat: admin user and permission management`.

### Task 7: Seed script + static serving + run scripts

**Files:**
- Create: `backend/seed.py`, `run_dev.bat`, `README.md`
- Modify: `backend/app.py` (serve `frontend/dist` at `/` with SPA fallback when it exists), `backend/config.py`

**Interfaces:**
- Produces: `python backend/seed.py [--force]` — refuses if users exist unless `--force` (drops & recreates). Seeds per spec §8: admin/admin123, dana/dana123, yossi/yossi123; 8 skills (AI/automation themed, categories: document-processing, data-extraction, reporting, integration), each 2–3 versions; ≥10 relationships covering all 4 types; permissions: dana edit×3 + read×2, yossi read×3, ≥2 skills invisible to yossi.
- `run_dev.bat`: starts Flask (`.venv\Scripts\python.exe backend\app.py`) and `npm run dev` in `frontend/`.

**Steps:**

- [ ] Write seed, run it, verify by logging in via test client as each user and asserting visible counts (quick pytest `test_seed.py` optional — verify via manual API calls instead is acceptable; if scripted, mark it `@pytest.mark.seed` and exclude from default run).
- [ ] Add static-serving route: if `frontend/dist/index.html` exists, `GET /<path>` serves file or falls back to `index.html` (except `/api/*`).
- [ ] Commit `feat: demo seed data and dev run scripts`.

### Task 8: Frontend scaffold + auth + API client

**Files:**
- Create: `frontend/` (Vite react template), `frontend/vite.config.js` (proxy `/api`→`http://localhost:5000`), `frontend/src/api/client.js`, `frontend/src/auth/AuthContext.jsx`, `frontend/src/auth/LoginPage.jsx`, `frontend/src/App.jsx` (router + protected layout with top nav: Dashboard, Graph, Admin[if admin], user chip + logout), `frontend/src/styles.css`

**Interfaces:**
- Produces: `api.get/post/put/del(path, body)` — fetch with `credentials: 'include'`, throws `ApiError(status, message)` from `{error}` json; on 401 fires `onUnauthorized` callback. `useAuth()` → `{user, login(u,p), logout(), loading}`; on mount calls `/api/auth/me`. Routes: `/login`, `/` dashboard, `/skills/:id`, `/graph`, `/admin` (admin only). Unauthed → redirect `/login`.
- Design: clean modern light UI, plain CSS in `styles.css` — CSS variables (accent `#2563eb`, surface `#f8fafc`, text `#0f172a`), system font stack, card/table components, status badges (draft=amber, active=green, deprecated=gray).

**Steps:**

- [ ] `npm create vite@latest frontend -- --template react`; add deps `react-router-dom cytoscape diff react-markdown`.
- [ ] Implement client, context, login page, routed shell. Verify: `npm run build` passes; with backend running + seed, login as admin works and nav renders (drive via Playwright or manual).
- [ ] Commit `feat: frontend shell with auth and routing`.

### Task 9: Dashboard

**Files:**
- Create: `frontend/src/pages/Dashboard.jsx`, `frontend/src/components/StatusBadge.jsx`, `frontend/src/components/TagChips.jsx`, `frontend/src/components/SkillFormModal.jsx`

**Interfaces:**
- Consumes: `GET /api/skills` with query params; `POST /api/skills`.
- Produces: search box (debounced `q`), dropdown filters (status, category, owner — built from loaded data), tag chip filter; table columns: name (link), description (truncated), category, tags, owner, status badge, updated, my_permission; "New Skill" button → modal (name, description, category, tags comma-input, status select, markdown content textarea) → POST → navigate to detail.

**Steps:**

- [ ] Implement; verify against seeded backend as admin (8 rows) and yossi (3 rows).
- [ ] Commit `feat: skills dashboard with search and filters`.

### Task 10: Skill detail — content, edit, links, history, diff, restore, audit

**Files:**
- Create: `frontend/src/pages/SkillDetail.jsx`, `frontend/src/components/VersionHistory.jsx`, `frontend/src/components/DiffView.jsx`, `frontend/src/components/LinksPanel.jsx`, `frontend/src/components/AuditPanel.jsx`, `frontend/src/components/RelationshipEditor.jsx`

**Interfaces:**
- Consumes: skill GET/PUT, versions, restore, audit, links, relationships POST/DELETE, `GET /api/skills` (for relationship target picker).
- Produces: header (name, badges, owner, category, tags, dates); tabs: **Content** (react-markdown render; Edit button if `my_permission==='edit'` → form incl. change-note → PUT), **Links** (outgoing/incoming grouped by type, each links to skill; RelationshipEditor: type select + target skill select + add; delete buttons; edit-only), **History** (version list; select two → DiffView using `diff.diffLines` rendering added/removed lines green/red; per-version Restore button with confirm → POST restore → refresh), **Audit** (table). Read-only users see no mutating controls.

**Steps:**

- [ ] Implement `DiffView` first: props `{oldText, newText}`, uses `diffLines`, `<pre>` rows classed `.diff-add`/`.diff-del`.
- [ ] Implement page + panels; verify with a seeded multi-version skill: diff shows changes, restore creates new version and updates content, links render, read-only user (yossi) sees no edit controls.
- [ ] Commit `feat: skill detail with versions, diff, restore, links, audit`.

### Task 11: Graph view

**Files:**
- Create: `frontend/src/pages/GraphView.jsx`, `frontend/src/graph/cyStyles.js`

**Interfaces:**
- Consumes: `GET /api/graph`.
- Produces: full-height Cytoscape canvas (`layout: cose`), nodes labeled by name + colored by category (fixed palette map), directed edges with arrowheads, edge label = type, edge color per type (`depends_on` red, `extends` blue, `used_with` green, `replaces` orange); zoom/pan native; tap node → highlight: selected + neighborhood keep full opacity, rest fade to 0.15 (class `.faded`); double-click (or "Open" button in side card) → navigate to `/skills/:id`; side panel filters: category checkboxes, tag select, relationship-type checkboxes — filtering hides non-matching nodes/edges (`display: none`); legend for edge colors.

**Steps:**

- [ ] Implement; verify as admin (8 nodes, all edges) and yossi (only visible subset); test node tap highlight and each filter.
- [ ] Commit `feat: interactive skill graph with filters and highlighting`.

### Task 12: Admin panel

**Files:**
- Create: `frontend/src/pages/AdminPanel.jsx`, `frontend/src/components/PermissionMatrix.jsx`

**Interfaces:**
- Consumes: users CRUD, `GET /api/users/<id>/permissions`, PUT permission, `GET /api/skills` (admin sees all).
- Produces: Users section (table: username, display name, role, created; create-user form; delete button w/ confirm, disabled for self); Permissions section: user selector → matrix of all skills × radio (None / Read / Edit) reflecting current rows, changes PUT immediately; note that owners/admins implicitly have edit (shown as disabled "owner" state).

**Steps:**

- [ ] Implement; verify: create user, grant read on one skill, log in as them, see exactly that skill; delete user.
- [ ] Commit `feat: admin panel for users and permission matrix`.

### Task 13: Polish, end-to-end verification, docs

**Files:**
- Modify: `README.md`, `frontend/src/styles.css`
- Create: (none)

**Steps:**

- [ ] Full pytest run green. `npm run build` green; run Flask alone serving `dist` and drive the whole app via browser (Playwright): login as all 3 users, dashboard filtering, edit→version→diff→restore, relationship add, graph filter+highlight, admin permission change reflected for target user.
- [ ] README: prerequisites, setup (`python -m venv .venv`, pip install, seed, npm install/build), run modes (dev two-process, demo single-process), demo credentials table, data-model note (short §4 summary).
- [ ] Commit `docs: README with setup and data model notes`.

## Self-Review Notes

- Spec coverage: §2✓(T1-2,6) §3✓(T1) §4✓(T1) §5✓(T2-6) §6✓(T8-12) §7✓(T1,T8) §8✓(T7) §9✓(T2-6,T13) §10 respected (no SKILL.md/i18n tasks).
- Types/signatures consistent across tasks (checked `my_permission`, links/graph shapes, service names).
- No TBD/placeholder steps; test intent stated concretely per task.
