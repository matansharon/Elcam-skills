# Elcam Skill Registry

An internal web application for managing organizational AI skills as first-class,
versioned objects — with role-based access control, typed skill relationships,
and an interactive dependency graph.

**Stack:** Flask + SQLAlchemy + SQLite (backend) · React + Vite (frontend) ·
session-cookie auth via Flask-Login · Cytoscape.js graph.

## Features

- **RBAC** — admin and regular users; per-skill `read` / `edit` / no-access
  permissions managed by admins. Non-admins only see skills they were granted.
  Skills a user cannot see return 404 (indistinguishable from nonexistent) and
  are excluded from lists, links, and the graph.
- **Versioned skills** — every save creates an immutable version (content +
  metadata snapshot + change note + author). Full history, side-by-side line
  diff between any two versions, and one-click restore. Restoring creates a
  *new* version; history is never rewritten.
- **Audit trail** — per-skill log of create/update/restore/delete, permission
  changes, and relationship changes.
- **Typed relationships** — directed links between skills: `depends_on`,
  `extends`, `used_with`, `replaces`. Shown on each skill's detail page
  (incoming + outgoing) and in an interactive graph with zoom/pan, per-type
  colored labeled edges, category/tag/type filters, click-to-open, and
  neighbor highlighting.
- **Dashboard** — searchable, filterable skill table (name/description search;
  status, category, owner, tag filters).
- **.skill package upload** — create a skill (or publish a new version of an
  existing one) by uploading a `.skill` file instead of writing markdown. A
  `.skill` file is a ZIP containing `SKILL.md` (YAML frontmatter with `name` +
  `description`, then the markdown body) plus optional bundled resources
  (`scripts/`, `references/`, …). The upload modal previews the parsed package
  before creating; the original archive is stored on the version it created,
  its bundled files are listed on the detail page, and it can be re-downloaded
  from the version history (doubles as export). Manual authoring still works —
  both paths coexist.
- **AI-assisted suggestions** — an optional "✨ Suggest with AI" button on
  both the manual and `.skill` upload create flows asks Claude to suggest a
  category, status, and tags, plus a related-skills picker pre-populated with
  candidate links (each with a suggested relationship type). Suggestions are
  editable before saving, and picked related skills become typed
  relationships on the new skill once it's created. The feature is optional —
  see the setup note below.

## Setup

Prerequisites: Python 3.10+, Node.js 18+.

```bat
:: 1. Python environment
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

:: 2. Frontend
cd frontend
npm install
npm run build
cd ..

:: 3. Demo data
.venv\Scripts\python.exe backend\seed.py --force
```

To enable AI-assisted suggestions, copy `backend/.env.example` to
`backend/.env` and set `ANTHROPIC_API_KEY` (optional `ANALYSIS_MODEL`,
default `claude-sonnet-5`). Without a key, clicking "✨ Suggest with AI"
reports that AI analysis is not configured, and everything else works as
before.

## Running

**Demo / single process** (Flask serves the built frontend):

```bat
.venv\Scripts\python.exe backend\app.py
```

Open http://localhost:5100 (set the `PORT` env var to change; 5000 is used by
another app on this machine).

**Development** (hot reload):

```bat
run_dev.bat
```

Starts Flask on :5100 and Vite on http://localhost:5173 (proxies `/api`).

**Tests:**

```bat
.venv\Scripts\python.exe -m pytest backend\tests -q
```

## Demo accounts

| Username | Password | Role  | Sees                                        |
| -------- | -------- | ----- | ------------------------------------------- |
| admin    | admin123 | admin | all 8 skills                                 |
| dana     | dana123  | user  | 7 skills (owns 2, edit on 3, read on 2)      |
| yossi    | yossi123 | user  | 3 skills (read only)                         |

## Data model (short)

Six tables (SQLite via SQLAlchemy, `backend/models.py`):

- **User** — username, password hash, display name, role (`admin`/`user`).
- **Skill** — current denormalized state: name (unique), description, owner,
  category, tags (JSON), status (`draft`/`active`/`deprecated`), timestamps.
  Deleting a skill cascades to everything below.
- **SkillVersion** — immutable snapshot per save: per-skill version number,
  all metadata fields + markdown content, change note, author, timestamp.
  Restore copies an old snapshot into a new version. Versions created from an
  uploaded `.skill` package also store the original archive bytes, its
  filename, and the list of bundled file paths (`backend/packages.py` parses
  uploads in memory; startup adds these columns to older databases
  automatically).
- **SkillPermission** — (user, skill) → `read`/`edit`. No row = no access.
  Admins and the skill's owner implicitly have edit.
- **SkillRelationship** — directed typed edge (source, target, type), unique
  per triple; self-links rejected.
- **AuditLog** — (skill, user, action, detail, timestamp).

## Architecture notes (swappability)

- **Auth** is isolated in `backend/auth.py` + `frontend/src/auth/` — replace
  session cookies with SSO/JWT without touching feature code.
- **Storage/permissions** logic lives in `backend/services.py` behind plain
  functions; blueprints stay thin.
- **Graph** endpoint (`/api/graph`) returns a generic `{nodes, edges}` shape,
  so Cytoscape can be swapped for another visualization library with no
  backend change.
- **API transport** is a single module (`frontend/src/api/client.js`).

Design specs: `docs/superpowers/specs/`
Implementation plans: `docs/superpowers/plans/`
