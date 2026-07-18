# Design: User Pages, Favorites & Folders

**Date:** 2026-07-18
**Status:** Approved (design), pending implementation plan

## Problem

The Skill Registry today presents skills as a single flat, filterable table on
the Dashboard. Three organizational capabilities are missing:

1. **No per-user home.** A user has no single place that gathers the skills they
   own (created or uploaded). Ownership is only reachable by filtering the
   Dashboard by owner.
2. **No favorites.** Users cannot mark skills they care about for quick return.
3. **No folder organization.** There is no way to group skills into an
   admin-curated hierarchy; the only grouping is by category/tag/status filters.

This design adds **user pages**, **per-user favorites**, and an
**admin-managed, hierarchical folder tree** with drag-and-drop and multi-folder
membership.

## Goals

- A personal page per user at `/users/:id` showing the skills they **own** plus
  their **favorites**. Users see their own page; **admins can open anyone's**.
- A private **favorite** (star) toggle on both Dashboard rows and the skill
  detail page, feeding each user's page.
- A single **global folder tree** (with subfolders) that **admins** create,
  rename, delete, and populate. Everyone else sees it read-only for navigation.
- Skills may belong to **multiple folders**. **Dragging** a skill onto a folder
  **moves** it (membership becomes exactly that folder); a per-skill
  **"Folders…"** checkbox menu (and bulk "Move to…") manages multi-membership.
- Clicking a folder shows **only its direct skills**, still filtered by each
  viewer's existing skill visibility.

## Non-goals

- Per-user private folders (the tree is global and admin-managed).
- Letting non-admins create/rename/delete folders or assign skills to folders.
- Recursive folder views (selecting a parent does **not** roll up subfolder
  skills — direct members only).
- Manual sibling ordering of folders (siblings are ordered by name; a
  `position` column is a possible later enhancement, out of scope here).
- Sharing/notifying on favorites; favorites are private per user.
- Changing the existing RBAC/visibility model for skills.

## Chosen approach

**Three new tables** — `Folder` (self-referential for subfolders),
`SkillFolder` (many-to-many join), and `Favorite` (per-user) — plus thin
additions to the existing blueprints. All folder mutations and skill→folder
assignment are gated to admins; favorites and the user page reuse the existing
`login_required` + role checks.

### Alternatives considered (folder model)

- **Single `folder_id` column on `Skill`.** Supports hierarchy but **not**
  multi-folder membership. Rejected — a skill must be able to live in several
  folders.
- **Reuse tags as pseudo-folders.** No nesting, no admin-only control, conflates
  two concepts. Rejected.
- **`Folder` + `SkillFolder` join (chosen).** The only model that satisfies both
  hierarchy and multi-membership cleanly.

## Data model — three new tables

Added to `backend/models.py`. New tables are created by the existing
`db.create_all()` in `create_app()`; **no `_migrate_schema()` change is needed**
(that helper only adds *columns* to pre-existing tables).

```
Folder
  id           INTEGER PK
  name         VARCHAR(120) NOT NULL
  parent_id    INTEGER FK → folders.id  NULLABLE   # NULL = top level
  created_by   INTEGER FK → users.id    NOT NULL
  created_at   DATETIME NOT NULL
  UNIQUE(parent_id, name)                          # sibling names unique

SkillFolder                                        # skill's folder memberships
  id           INTEGER PK
  skill_id     INTEGER FK → skills.id   NOT NULL
  folder_id    INTEGER FK → folders.id  NOT NULL
  UNIQUE(skill_id, folder_id)

Favorite
  id           INTEGER PK
  user_id      INTEGER FK → users.id    NOT NULL
  skill_id     INTEGER FK → skills.id   NOT NULL
  created_at   DATETIME NOT NULL
  UNIQUE(user_id, skill_id)
```

### Relationships & cascades

- `Folder.children` → self-referential (`parent_id`), `cascade="all, delete-orphan"`
  so deleting a folder deletes its subfolders recursively.
- `Folder.skill_links` → `SkillFolder`, `cascade="all, delete-orphan"` so deleting
  a folder removes memberships; **skills themselves survive** (become unfiled).
- `Skill` gains `folder_links` (`SkillFolder`) and `favorited_by` (`Favorite`),
  both `cascade="all, delete-orphan"`, so deleting a skill cleans up its
  memberships and favorites.
- `User` gains `favorites` (`Favorite`), `cascade="all, delete-orphan"`, so
  deleting a user removes their favorites.

### Serialization additions

- `Skill.to_dict()` gains a `favorited` boolean for the **current** user. Because
  `to_dict` has no request context, the caller passes it in:
  `to_dict(my_permission=..., favorited=<bool>)` (default `False`). List/detail
  handlers compute the current user's favorite skill-id set once and pass it per
  skill.
- The **detail** response additionally includes `folders`: a list of
  `{id, name}` for the folders the skill belongs to.

## Behavior rules

- **User page contents** = skills where the viewed user is `owner_id`, plus that
  user's favorites.
- **Favorites** are private per user; the star toggles only the current user's
  favorite. Favorite lists are filtered by the requester's skill visibility (a
  favorited skill the user can no longer see is omitted).
- **Folder tree** is one global structure. Only **admins** create/rename/
  delete/reparent folders and assign skills to folders. Non-admins see the tree
  read-only.
- **Drag a skill onto a folder = move**: its membership becomes exactly
  `[that folder]` (all other memberships removed). The per-skill **"Folders…"**
  checkbox menu sets exact membership and is where multi-folder assignment
  happens. Bulk-selected rows support "Move to…" (mode `move`) as well.
- **Clicking a folder shows only its direct skills** (non-recursive), still
  filtered by `visible_skills(current_user)`.
- **Deleting a folder** cascades to subfolders and removes memberships after a
  confirmation dialog that shows affected subfolder/skill counts.
- **Reparenting** rejects cycles: a folder cannot be moved under itself or any
  of its descendants (returns 400).

## Architecture

### 1. Backend — folders (`backend/folders.py`, new blueprint)

Business logic lives in `backend/services.py` (following the existing thin-
blueprint pattern); the blueprint stays thin. Admin gating via a small
`require_admin()` helper (abort 403 for non-admins).

```
GET    /api/folders            # all users. Full tree as a flat list of
                               # {id, name, parent_id, skill_count} where
                               # skill_count = memberships visible to the
                               # requester. Frontend nests by parent_id.
POST   /api/folders            # admin. {name, parent_id?} → created folder.
                               # 400 on duplicate sibling name / bad parent.
PUT    /api/folders/:id        # admin. {name?, parent_id?}. Reparent guards
                               # against cycles (400) and duplicate names.
DELETE /api/folders/:id        # admin. Cascade subfolders, unfile skills.
```

Skill↔folder membership (admin-only), added to the skills blueprint:

```
PUT  /api/skills/:id/folders   # {folder_ids:[...]} set exact membership.
                               # Drag/menu use this; [] unfiles the skill.
POST /api/folders/:id/skills   # {skill_ids:[...], mode:"move"|"add"} bulk.
                               # "move": each skill's membership becomes
                               # exactly [folder_id]; "add": folder_id added.
```

Assignment endpoints validate each skill exists and 400/404 appropriately;
folder-ids are validated to exist. Audit: folder create/rename/delete and
skill assignment are **not** added to the per-skill `AuditLog` (which requires a
`skill_id` and is skill-scoped); they will surface in the global `ActivityLog`
via the existing `after_request` hook like any other write. (Optional readable
summaries can be added later; not required for this feature.)

### 2. Backend — favorites (added to `backend/skills.py`)

```
GET    /api/favorites              # current user's favorited skills, as skill
                                   # dicts, filtered by visibility, newest first.
PUT    /api/skills/:id/favorite    # idempotent add; returns {favorited: true}.
DELETE /api/skills/:id/favorite    # remove; returns {favorited: false}.
```

Favoriting requires the skill to be **visible** to the user
(`get_visible_skill_or_404`); you cannot favorite a skill you can't see.

### 3. Backend — user page (added to `backend/users.py`)

```
GET /api/users/:id             # self or admin (else 404, matching the app's
                               # "invisible == nonexistent" convention).
                               # → {id, display_name, username, role,
                               #    created_at, owned_count, favorite_count}
GET /api/users/:id/favorites   # self or admin. That user's favorites as skill
                               # dicts, filtered by the *requester's* visibility.
```

"Skills they own" reuses the existing `GET /api/skills?owner=<id>` (already
visibility-filtered; an owner always sees their own skills, an admin sees all).

### 4. Services (`backend/services.py`) additions

- `visible_folder_tree(user)` → list of folder dicts with per-viewer
  `skill_count` (count of memberships whose skill is in `visible_skills(user)`).
- `create_folder / rename_or_reparent_folder / delete_folder` with sibling-name
  and cycle validation.
- `set_skill_folders(skill, folder_ids)` and `bulk_assign(folder, skill_ids, mode)`.
- `toggle_favorite(user, skill, on: bool)` and `favorite_skill_ids(user)`.
- A `require_admin(user)` helper mirroring `require_edit`.

### 5. Frontend

**Dashboard (`frontend/src/pages/Dashboard.jsx`)** gains a collapsible left
**folder sidebar**:

```
┌ Folders ─────────┐   Skills (filtered by selection)
│ ★ All skills     │   ┌───────────────────────────────────────┐
│ ⌫ Unfiled        │   │ ☆  Name    Desc   Cat  Owner  Status  │
│ ▸ Frontend  (12) │   │ ★  ...                                 │
│ ▾ Backend    (7) │   └───────────────────────────────────────┘
│    • Auth    (3) │   [admin] ☑ bulk-select → "Move to…"
│    • Data    (4) │   drag a row onto a folder = move
│ + New folder     │   ⋯ per-folder: rename / new subfolder / delete
└──────────────────┘
```

- **"All skills"** (default) = current flat visible list. **"Unfiled"** = skills
  with no folder membership. Selecting a folder filters the table to that
  folder's direct, visible skills (client-side filter over the fetched list, or
  a `folder=<id>` query param — implementation detail for the plan).
- **Admins** get: `+ New folder`, per-folder `⋯` menu (rename / new subfolder /
  delete-with-confirm), **drag** a skill row onto a folder (move), a per-row
  **"Folders…"** checkbox popover, and **bulk-select** rows → "Move to…".
- **Non-admins** see the same tree with counts but none of the mutate controls.
- New components (indicative): `FolderTree.jsx`, `FolderMenu.jsx` (per-skill
  checkbox popover), `MoveToFolderBar.jsx` (bulk action bar).

**Favorites star** ☆/★ on each Dashboard row and the `SkillDetail` header,
calling the favorite endpoints and reflecting `favorited` optimistically.

**User page (`frontend/src/pages/UserPage.jsx`, route `/users/:id`)**: profile
header (display name, role, joined date, owned/favorite counts) + a **"Skills I
own"** section + a **"Favorites"** section, each a compact skill table reusing
existing row rendering. A **"My Page"** link in the top nav (to
`/users/<currentUser.id>`), and **owner display names become links** to user
pages (Dashboard rows, skill detail). Admins reach other users' pages via those
links.

**API client (`frontend/src/api/client.js`)**: add the folder, favorite, and
user-page calls.

## Permissions & visibility recap

| Action | Who |
|---|---|
| View folder tree | All logged-in users (read-only for non-admins) |
| Create/rename/delete/reparent folder | Admin only |
| Assign skill(s) to folder(s) | Admin only |
| Skills shown within a folder | Filtered by each viewer's skill visibility |
| Toggle a favorite | Any user, on skills they can see; affects only their own |
| View a user page (`/users/:id`) | The user themselves, or an admin |
| View a user's favorites | The user themselves, or an admin |

## Edge cases

- **Delete folder with contents:** subfolders deleted recursively, memberships
  removed, **skills survive** (become unfiled). UI confirms with counts.
- **Reparent into own descendant / self:** rejected (400).
- **Duplicate sibling name:** rejected (400) on create and reparent/rename.
- **Favorite then lose access:** the `Favorite` row may persist harmlessly but
  is **omitted** from favorite lists because they are visibility-filtered.
- **Skill deleted:** its `SkillFolder` and `Favorite` rows cascade away.
- **User deleted:** their `Favorite` rows cascade away.
- **Non-admin hits a mutate endpoint:** 403 (`require_admin`).
- **Drag move on a multi-folder skill:** all prior memberships replaced by the
  single target folder (this is the intended "move" semantics).

## Testing

**Backend (`backend/tests/`, pytest):**

- Folder CRUD happy paths + **admin-only** enforcement (403 for non-admins).
- Reparent **cycle rejection** and duplicate-sibling-name rejection.
- Membership: `set_skill_folders` exact-set, bulk `move` vs `add`, unfile via `[]`.
- `GET /api/folders` `skill_count` reflects **per-viewer** visibility.
- Favorites: add/remove idempotency, `favorited` flag in skill dicts, favorite
  list **visibility filtering**, cannot favorite an invisible skill (404).
- User page access control: self (200), admin viewing another (200), non-admin
  viewing another (404); payload counts correct.
- Cascades: deleting a skill/folder/user cleans up the expected rows.

**Frontend:** keep light — verify the star toggle round-trips and folder
selection filters the table. Drag-and-drop verified manually.

## Rollout / compatibility

Purely additive: no existing columns change, no existing endpoint contracts
break (only additive fields in `skill.to_dict`). Existing databases pick up the
three new tables automatically via `db.create_all()` on next startup. `seed.py`
may optionally seed a couple of demo folders and favorites for the demo accounts
(nice-to-have, decided in the plan).
