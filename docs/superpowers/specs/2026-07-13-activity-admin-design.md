# Design: Activity Admin Panel (global operation logging)

**Date:** 2026-07-13
**Status:** Approved (design), pending implementation plan

## Problem

The Skill Registry captures only a narrow slice of activity: the existing
`AuditLog` model records a subset of *write* operations (create, update,
upload, restore, permission changes, relationship changes) and is scoped
**per skill** (`skill_id` is non-nullable). There is no global view of what
users are doing across the app, and passive operations (reads, searches,
logins, failed logins, downloads, AI usage) are never recorded.

We want a standalone admin/activity page that records **all operations across
the whole app** and is gated by a **credential stored in `backend/.env`** —
deliberately independent of the app's existing DB-backed `admin` role.

## Goals

- Record **every** backend API request automatically (raw view).
- Enrich meaningful business/auth events with human-readable descriptions
  (readable view).
- Expose a page, gated by a separate `.env` credential, to browse the log
  with filters/search, summary stats, auto-refresh, and CSV export.
- Leave the existing per-skill audit panel (skill detail page) untouched.

## Non-goals

- Replacing or migrating the existing per-skill `AuditLog`. The new log is
  additive.
- Multi-user roles/permissions on the activity page itself (single shared
  `.env` credential).
- Rate-limiting / brute-force lockout on the `.env` login (out of scope;
  failed attempts are logged).
- Storing request bodies or query strings (never captured — see Security).

## Chosen approach

**One `ActivityLog` table populated by a global `after_request` hook.**

A single Flask `after_request` hook fires on every `/api/*` call and writes
one row (who, method, path, status, duration, IP, timestamp). For meaningful
events, the handler — via the already-centralized `services.log_action` and a
few auth-event calls — stashes a readable `summary`/`category` on `flask.g`,
which the hook folds into the **same** row. One write per request, one table,
both views (raw + readable) from one source.

### Alternatives considered

- **Two tables** (raw request log + generalized existing `AuditLog`): forces a
  schema change on the existing per-skill audit and makes the hybrid toggle
  merge two tables. More moving parts, same result. Rejected.
- **Raw log only, derive readable text on the frontend**: cannot show a
  skill's *name* or *which* user got a permission (only path IDs), and cannot
  distinguish "wrong password" from "unknown user." Too lossy. Rejected.

## Architecture

### 1. The `.env` gate (independent of DB users)

- **Config** (`config.py`): read `ADMIN_PANEL_USER` and
  `ADMIN_PANEL_PASSWORD`. If either is unset, the panel is **disabled**:
  login always fails (no insecure default).
- **Blueprint** `activity_bp` at `/api/activity`:
  - `POST /api/activity/login` — verify credentials with a constant-time
    compare (`hmac.compare_digest` on both username and password). On success,
    set `session['activity_admin'] = True`. On failure, return 401.
  - `POST /api/activity/logout` — clear `session['activity_admin']`.
  - `GET /api/activity/session` — report whether the current session holds the
    activity-admin flag (so the frontend can restore state on reload).
- **Guard**: an `@activity_required` decorator on every non-login activity
  endpoint returns 401 unless `session.get('activity_admin')` is true. This is
  completely independent of Flask-Login / `current_user`; a DB `admin` gets no
  automatic access, and the activity admin needs no DB user.

### 2. Data model — `ActivityLog`

New model in `models.py`:

| column        | type                | notes                                            |
|---------------|---------------------|--------------------------------------------------|
| id            | Integer PK          |                                                  |
| timestamp     | DateTime            | default `utcnow`                                 |
| user_id       | Integer FK users.id | nullable (anonymous / failed login / .env admin) |
| actor         | String(120)         | denormalized: DB display name, "owner" (.env admin), or "anonymous" |
| method        | String(10)          | GET/POST/PUT/DELETE                              |
| path          | String(255)         | path only, **no query string**                  |
| status_code   | Integer             |                                                  |
| duration_ms   | Integer             | request wall time                               |
| ip_address    | String(45)          | supports IPv6                                    |
| summary       | Text                | nullable, human-readable (readable view)         |
| category      | String(20)          | nullable: auth / skill / permission / relationship / admin |

`actor` is denormalized because failed logins have no user and the `.env`
admin is not a DB row. `to_dict()` returns all fields ISO-formatted.

Created via `db.create_all()`; the app already runs a lightweight
`_migrate_schema()` on boot, but since this is a brand-new table no ALTER is
needed for existing databases (the table is simply created).

### 3. Capture mechanism

- `before_request`: stamp `g._activity_start` (a monotonic start time).
- `after_request`: for any request whose path starts with `/api/`, write one
  `ActivityLog` row:
  - `actor`/`user_id`: `current_user` if authenticated; else "owner" if the
    `activity_admin` session flag is set; else "anonymous".
  - `duration_ms`: now − `g._activity_start`.
  - `summary`/`category`: read from `g.activity_summary` / `g.activity_category`
    if a handler set them; else null (pure raw row).
  - The write is best-effort: wrapped so a logging failure never breaks the
    actual API response (log and swallow).
- **Readable summaries**:
  - `services.log_action(...)` already centralizes skill/permission/
    relationship events. It will *additionally* set `g.activity_summary` and
    `g.activity_category` (last call wins for the request's headline summary;
    the granular per-skill `AuditLog` rows are unchanged).
  - Auth events set summaries directly in `auth.py`: `login` success
    ("Signed in"), `login` failure ("Failed login for '<username>'"),
    `logout` ("Signed out"), all `category="auth"`.
  - `.env` panel login/logout set summaries in `activity.py`
    (`category="admin"`), e.g. "Admin-panel sign-in", "Failed admin-panel
    login".

### 4. Read/query API (all `@activity_required`)

- `GET /api/activity/logs` — server-side paginated + filtered list.
  Query params: `page`, `page_size` (capped, e.g. ≤200), `actor`,
  `category`, `method`, `status`, `date_from`, `date_to`, `q` (free-text over
  `path`+`summary`), `view` (`raw`|`readable`; `readable` returns only rows
  that have a `summary`). Response: `{ items, page, page_size, total }`.
- `GET /api/activity/stats` — summary metrics for the dashboard cards:
  total events, distinct active users, top actions (grouped by
  category/summary), and an events-over-time bucket series (e.g. per hour/day
  over a recent window). Honors the same filters as `logs`.
- `GET /api/activity/export.csv` — the current filtered set as CSV
  (streamed), same filter params as `logs`, no pagination.
- `POST /api/activity/clear` — purge all rows (manual retention control).
  Returns count deleted. This action is itself logged (category="admin").

### 5. Retention

- Keep everything by default; the list is paginated.
- Optional env cap `ACTIVITY_LOG_MAX_ROWS` (default off/unset): after each
  write, if the row count exceeds the cap, trim the oldest rows down to the
  cap. Cheap and bounded when configured.
- Manual "Clear log" button → `POST /api/activity/clear`.

### 6. Frontend

- **Route**: `/activity`, rendered **outside** the main authenticated app
  shell (`Layout`) and **not** shown in the main nav. It has its own minimal
  login screen.
- **State**: a tiny local context/hook that calls `GET /api/activity/session`
  on load to decide login vs. panel; `POST .../login` and `.../logout` manage
  it. Independent of `AuthContext`.
- **Panel UI**:
  - Summary stat cards + a small activity-over-time chart (from `/stats`).
  - **Raw ⇄ Readable** toggle (drives the `view` param).
  - Filters: actor, category, method, status, date range; free-text search.
  - **Auto-refresh** toggle (poll ~5s) — refetches `logs` + `stats`.
  - **Export CSV** button (hits `export.csv` with current filters).
  - **Clear log** button (confirm dialog).
  - Server-side pagination controls.
- Reuses existing styling primitives (`card`, `panel`, `data` table, `badge`,
  `banner`) from `styles.css`.

## Security considerations

- Constant-time credential comparison (`hmac.compare_digest`) for the `.env`
  login; panel disabled when env vars are unset (no default password).
- The raw log stores **method + path only** — never request bodies and never
  query strings — so credentials (in the login body) and any sensitive query
  data are never persisted. `path` is `request.path` (already excludes the
  query string).
- Failed `.env` logins and failed DB logins are both recorded, giving an
  audit trail of access attempts.
- Activity endpoints are gated solely by the `activity_admin` session flag,
  orthogonal to the app's user session.

## Testing strategy

- **Config/gate**: login succeeds only with correct env credentials;
  disabled when env unset; `@activity_required` returns 401 without the flag;
  logout clears it; constant-time compare in place.
- **Capture**: an authenticated API call writes exactly one `ActivityLog`
  row with correct actor/method/path/status/duration; an anonymous call logs
  actor="anonymous"; a failed DB login logs a row with a readable summary and
  no `user_id`; body/query never appear in the stored row.
- **Summaries**: creating/editing a skill yields a readable `summary` +
  `category="skill"`; permission change → `category="permission"`; the
  per-skill `AuditLog` still gets its granular rows (regression).
- **Query API**: pagination bounds, each filter, free-text `q`, `view=raw`
  vs `view=readable`, stats aggregation shape, CSV contents/escaping.
- **Retention**: `ACTIVITY_LOG_MAX_ROWS` trims oldest; `clear` empties and
  logs itself.
- **Frontend**: session restore on reload, login/logout, toggle switches the
  view, filters/search drive requests, auto-refresh polling, CSV download,
  clear with confirmation.

## Affected / new files (anticipated)

- `backend/config.py` — new env vars.
- `backend/models.py` — `ActivityLog` model.
- `backend/activity.py` — new blueprint (login/logout/session/logs/stats/
  export/clear + `@activity_required`).
- `backend/app.py` — register blueprint; `before_request`/`after_request`
  hooks; optional retention trim.
- `backend/services.py` — `log_action` also sets `g.activity_summary`/
  `g.activity_category`.
- `backend/auth.py` — set summaries for login/logout/failed login.
- `backend/.env.example` — document `ADMIN_PANEL_USER`,
  `ADMIN_PANEL_PASSWORD`, `ACTIVITY_LOG_MAX_ROWS`.
- `frontend/src/App.jsx` — add the `/activity` route outside `Layout`.
- `frontend/src/activity/` — `ActivityLogin.jsx`, `ActivityPanel.jsx`, and a
  small session hook/context; plus a stat-cards + chart component.
- Tests under `backend/` (pytest) and any frontend test setup already in use.
