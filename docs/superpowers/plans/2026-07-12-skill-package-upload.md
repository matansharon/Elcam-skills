# Skill Package (.skill) Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users can create skills and publish new versions by uploading `.skill` ZIP packages; the original archive is stored per version and downloadable.

**Architecture:** A pure in-memory parser module (`backend/packages.py`) validates the ZIP and extracts SKILL.md frontmatter/body. Three nullable columns on `skill_versions` hold the archive. Two upload endpoints + one download endpoint join the existing skills blueprint. The React app gains an upload modal (with server-side dry-run preview) on the dashboard and an upload-new-version modal in the History tab.

**Tech Stack:** Flask, PyYAML, zipfile (stdlib), SQLite BLOB; React (no new frontend deps).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-12-skill-package-upload-design.md`
- Run tests with `.venv\Scripts\python.exe -m pytest backend/tests -q` from repo root
- Never add AI attribution to commits
- Existing 42 tests must stay green after every task
- Backend port 5100; frontend dev proxy already points there

---

### Task 1: Model columns, migration, PyYAML dependency

**Files:**
- Modify: `backend/requirements.txt`, `backend/models.py`, `backend/app.py`
- Test: `backend/tests/test_upload.py` (new)

**Interfaces:**
- Produces: `SkillVersion.package_blob/package_filename/bundled_files` columns; `to_dict()` keys `has_package`, `package_filename`, `bundled_files`.

- [ ] Add `pyyaml>=6.0` to requirements; `pip install`
- [ ] Failing test: version dict of a manual skill has `has_package: False`, `bundled_files: []`
- [ ] Add the three nullable columns + to_dict keys; startup PRAGMA/ALTER migration in `create_app`
- [ ] Tests pass; commit

### Task 2: Parser + `POST /api/skills/upload` (create + dry_run + rejections)

**Files:**
- Create: `backend/packages.py`
- Modify: `backend/services.py` (add `create_skill_from_package`), `backend/skills.py`
- Test: `backend/tests/test_upload.py`

**Interfaces:**
- Produces: `parse_package(file_bytes, filename) -> {name, description, content, bundled_files}` (aborts 400 on invalid); `create_skill_from_package(user, parsed, file_bytes, filename, category, tags, status) -> Skill`; test helper `make_package(name, description, body, extra_files=None, root_dir=None) -> bytes`.

- [ ] Failing tests: happy-path create (fields from frontmatter, v1 has package, audit `create` mentions package), root-level SKILL.md accepted, dry_run creates nothing, rejects non-zip / no SKILL.md / no frontmatter / no name / duplicate name / oversized (403 not needed here — login only)
- [ ] Implement parser (size guards, SKILL.md discovery root or one dir deep, UTF-8, YAML frontmatter split) and endpoint (multipart `file`, form `category`/`tags` CSV/`status`/`dry_run`)
- [ ] Tests pass; commit

### Task 3: `POST /api/skills/<id>/upload` — new version from package

**Files:**
- Modify: `backend/services.py` (add `create_version_from_package`), `backend/skills.py`
- Test: `backend/tests/test_upload.py`

**Interfaces:**
- Produces: `create_version_from_package(user, skill, parsed, file_bytes, filename, change_note="") -> SkillVersion` — sets description+content from package, leaves name/category/tags/status untouched, bumps `updated_at`, audit `upload`.

- [ ] Failing tests: creates version N+1 with package attached; description/content updated; name/category/tags/status untouched; default change note `Uploaded package '<file>'`; 403 for read-only user; 404 for invisible skill
- [ ] Implement service + endpoint
- [ ] Tests pass; commit

### Task 4: `GET /api/skills/<id>/versions/<n>/package` — download

**Files:**
- Modify: `backend/skills.py`
- Test: `backend/tests/test_upload.py`

- [ ] Failing tests: returns original bytes with `application/zip` + attachment filename; 404 for manual version, missing version, invisible skill
- [ ] Implement with `send_file(BytesIO(...), as_attachment=True, download_name=...)`
- [ ] Tests pass; full suite green; commit

### Task 5: Frontend — upload modal on dashboard

**Files:**
- Modify: `frontend/src/api/client.js` (add `api.upload`), `frontend/src/pages/Dashboard.jsx`, `frontend/src/styles.css`
- Create: `frontend/src/components/UploadSkillModal.jsx`

**Interfaces:**
- Produces: `api.upload(path, formData)` — fetch POST multipart, same ApiError handling; `<UploadSkillModal onCreated={skill=>...} onClose={...}/>`.

- [ ] `api.upload` helper
- [ ] UploadSkillModal: file input → dry-run preview (name, description, content snippet, bundled-file chips) → category/tags/status fields → create → `onCreated(skill)`
- [ ] Dashboard: "Upload .skill" button opens it; navigate to new skill on success
- [ ] `npm run build` green; commit

### Task 6: Frontend — upload new version, download links, bundled files

**Files:**
- Modify: `frontend/src/components/VersionHistory.jsx` (upload-new-version modal + package chips), `frontend/src/pages/SkillDetail.jsx` (Download .skill header button, bundled-files list under content), `frontend/src/styles.css`

- [ ] VersionHistory: "Upload new version" button (canEdit) → modal (file + change note) → POST → `onUploaded()`; package chip `<a>` per version with `has_package`
- [ ] SkillDetail: header "Download .skill" when latest has package; bundled files listed under Content tab
- [ ] `npm run build` green; commit

### Task 7: Docs, verification, merge

- [ ] README: upload feature section + pyyaml note
- [ ] Full pytest suite + `npm run build`
- [ ] Browser E2E with the real `file-inventory-summary.skill`: upload-create, preview, new-version upload, download, read-only user sees no upload buttons
- [ ] Merge branch to main (--no-ff), push
