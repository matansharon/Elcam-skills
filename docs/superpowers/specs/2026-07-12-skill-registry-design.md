# Skill Registry MVP — Design Spec

**Date:** 2026-07-12
**Status:** Approved by user
**Project:** Elcam-Skills — organizational AI Skill Registry web application

## 1. Purpose

An internal web application for managing organizational AI skills as first-class, versioned objects with role-based access control, typed inter-skill relationships, and an interactive graph visualization. MVP scope: demonstrable immediately with seed data.

## 2. Decisions (user-confirmed)

| Decision | Choice |
|---|---|
| Stack | Flask + React (Vite) + SQLite |
| UI language | English only |
| SKILL.md import/export/sync | Out of scope for MVP (storage kept modular for later) |
| Auth mechanism | Session cookies via Flask-Login (not JWT) |

## 3. Architecture

Single repo, two modules:

```
Elcam-Skills/
├── backend/
│   ├── app.py              # app factory, blueprint registration
│   ├── models.py           # SQLAlchemy models
│   ├── services.py         # thin service layer (versioning, permissions, audit)
│   ├── auth.py             # auth blueprint (login/logout/me) + Flask-Login setup
│   ├── users.py            # admin blueprint: user CRUD, permission assignment
│   ├── skills.py           # skills blueprint: CRUD, versions, diff, restore
│   ├── relationships.py    # relationship CRUD + graph endpoint
│   ├── seed.py             # demo data seeder
│   ├── requirements.txt
│   └── tests/              # pytest API tests
├── frontend/               # React + Vite SPA
│   └── src/
│       ├── api/            # fetch wrapper (single module — swappable transport)
│       ├── auth/           # AuthContext + login page (isolated for later swap)
│       ├── pages/          # Dashboard, SkillDetail, GraphView, AdminPanel
│       └── components/
└── docs/superpowers/specs/
```

- **Dev:** Flask on :5000, Vite dev server on :5173 with proxy of `/api` → :5000.
- **Demo/prod:** `npm run build`; Flask serves `frontend/dist` as static files (single process).
- Session-cookie auth; all API routes under `/api/*`; non-admin requests are filtered by permission at the service layer.

## 4. Data Model

SQLite via SQLAlchemy. Six tables:

**User** — `id, username (unique), password_hash (werkzeug), display_name, role ('admin'|'user'), created_at`.

**Skill** — `id, name, description, owner_id → User, category, tags (JSON array), status ('draft'|'active'|'deprecated'), created_at, updated_at`. Holds *current* denormalized values for fast list/filter queries. Deleting a skill cascades to its versions, permissions, relationships, and audit rows.

**SkillVersion** — `id, skill_id → Skill, version_number (per-skill, monotonic), name, description, category, tags, status, content (markdown), change_note, created_by → User, created_at`. Immutable snapshot of content **and** metadata at each save. Restore copies an old snapshot into a **new** version (history is never mutated or deleted).

**SkillPermission** — `id, user_id → User, skill_id → Skill, level ('read'|'edit')`, unique on (user, skill). Semantics: no row ⇒ no access. Admins implicitly see/edit everything. A skill's owner implicitly has edit. Only admins manage permissions.

**SkillRelationship** — `id, source_skill_id → Skill, target_skill_id → Skill, type ('depends_on'|'extends'|'used_with'|'replaces'), created_by, created_at`, unique on (source, target, type). Directed. Self-links rejected.

**AuditLog** — `id, skill_id → Skill, user_id → User, action, detail (text), created_at`. Actions: create, update (new version), restore, delete, permission_set, permission_removed, relationship_added, relationship_removed.

## 5. API Surface (all `/api/...`, JSON)

- **Auth:** `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`.
- **Users (admin only):** `GET/POST /users`, `DELETE /users/<id>`, `GET /users/<id>/permissions`, `PUT /users/<id>/permissions/<skill_id>` (level or remove).
- **Skills:** `GET /skills` (search `q`, filters: tag, category, owner, status — returns only skills the caller can read), `POST /skills` (any authenticated user; creator becomes owner), `GET/PUT/DELETE /skills/<id>` (PUT requires edit ⇒ creates new version; DELETE owner/admin only).
- **Versions:** `GET /skills/<id>/versions`, `GET /skills/<id>/versions/<n>`, `POST /skills/<id>/versions/<n>/restore` (edit permission).
- **Audit:** `GET /skills/<id>/audit` (read permission).
- **Relationships:** `POST /relationships`, `DELETE /relationships/<id>` (edit on source skill), `GET /skills/<id>/links` (incoming + outgoing).
- **Graph:** `GET /graph` → generic `{nodes: [{id, name, category, tags, status}], edges: [{id, source, target, type}]}` limited to skills the caller can read (edges only where both endpoints visible). Generic shape keeps the frontend graph library swappable.

Version diffing is computed client-side with `jsdiff` from two fetched version snapshots (keeps backend simple; server stores canonical data only).

## 6. Frontend Screens

- **Login** — username/password form.
- **Dashboard** — table of visible skills; text search; filters for tag, category, owner, status; create-skill button.
- **Skill detail** — rendered markdown content, metadata, status badge; incoming/outgoing links grouped by relationship type; edit form (with change note); version history list; version viewer with side-by-side/inline diff (jsdiff) between any two versions; restore button per version; audit trail panel; relationship editor (users with edit).
- **Graph view** — Cytoscape.js: all visible skills as nodes, labeled directed edges per relationship type (color/style per type); zoom/pan; click node → open skill detail; filter by category, tag, relationship type; selecting a node highlights its direct neighbors and fades the rest.
- **Admin panel** (admin only) — user list, create/delete user, role assignment; per-user permission editor: for a chosen user, set read/edit/none per skill.

Plain CSS (no framework dependency) with a clean modern look; UI chrome in English.

## 7. Error Handling

- API returns consistent JSON errors `{error: message}` with proper status codes: 401 unauthenticated, 403 forbidden (no/insufficient permission), 404 not found (including skills the user cannot see — indistinguishable from nonexistent for non-admins), 400 validation.
- Frontend surfaces errors as inline banners/toasts; 401 redirects to login.
- Concurrency: last-write-wins on skill save (acceptable for MVP; every save is versioned so nothing is lost).

## 8. Seed Data (`backend/seed.py`)

- Users: `admin/admin123` (admin), `dana/dana123`, `yossi/yossi123` (regular).
- 8 example AI skills across categories (e.g., document-processing, data-extraction, reporting, integration), each with 2–3 versions to demonstrate history/diff/restore.
- ~10 relationships covering all four types.
- Mixed permissions: dana has edit on some skills and read on others; yossi has read on a subset and no access to at least two — so RBAC filtering is visibly demonstrable in dashboard and graph.
- Seeder is idempotent (recreates DB or refuses if data exists — refuses with a `--force` flag to recreate).

## 9. Testing

pytest against the Flask app (test client, temp SQLite):
- Auth: login/logout/me, wrong password, unauthenticated access → 401.
- RBAC: listing filtered by permission; read vs edit vs no access on every mutating endpoint; admin bypass; owner implicit edit; non-admin cannot manage users/permissions.
- Versioning: save creates version N+1; snapshots immutable; restore creates a new version with old content; version list ordering.
- Relationships: create/delete, self-link rejection, duplicate rejection, links endpoint, graph visibility filtering.
- Audit: entries written for each audited action.

Frontend verified by driving the built app end-to-end (no unit tests in MVP).

## 10. Out of Scope (MVP)

SKILL.md import/export and folder sync; skill-group/category-level permissions (per-skill only); email/SSO auth; file attachments on skills; Hebrew/RTL UI; real-time collaboration; pagination (dataset is small).
