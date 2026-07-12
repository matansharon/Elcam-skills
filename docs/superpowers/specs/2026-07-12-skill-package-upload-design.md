# Skill Package (.skill) Upload — Design

Date: 2026-07-12
Status: Approved

## Goal

Let users create skills — and publish new versions of existing skills — by
uploading `.skill` package files instead of hand-writing markdown. Manual
authoring stays available; upload is an additional path.

## The .skill format

A `.skill` file is a ZIP archive. Canonical layout:

```
<skill-name>/
  SKILL.md          <- required
  scripts/…         <- optional bundled resources
  references/…      <- optional
```

`SKILL.md` starts with YAML frontmatter delimited by `---` lines, containing
at least `name` and `description` (folded `>-` scalars allowed), followed by
the markdown body:

```markdown
---
name: file-inventory-summary
description: >-
  Scan a folder recursively and generate …
---

# File Inventory Summary
…body…
```

We accept `SKILL.md` either inside a single top-level directory (canonical) or
at the archive root. If multiple `SKILL.md` files exist, the shallowest one
wins; ties are ambiguous → reject.

## Decisions (user-confirmed)

1. **Upload alongside manual authoring** — both paths coexist; editing via the
   form keeps working on uploaded skills.
2. **Store the package** — the original archive bytes are kept on the version
   that the upload created, with the list of bundled file paths; the archive
   is downloadable (doubles as export).
3. **Upload-as-new-version** — users with edit permission can upload a `.skill`
   file on the detail page to create version N+1.

## Data model

Three nullable columns on `skill_versions` (no new table — a package belongs
to exactly the version its upload created):

| column             | type        | meaning                                   |
|--------------------|-------------|-------------------------------------------|
| `package_blob`     | LargeBinary | raw bytes of the uploaded archive          |
| `package_filename` | String(255) | original upload filename                   |
| `bundled_files`    | JSON        | list of member paths inside the archive    |

Manually-authored versions leave all three NULL. `SkillVersion.to_dict()`
gains `has_package` (bool), `package_filename`, and `bundled_files` — never
the blob itself.

**Migration:** `db.create_all()` does not add columns to existing tables. At
startup, `create_app` runs a lightweight SQLite migration: `PRAGMA
table_info(skill_versions)`, then `ALTER TABLE … ADD COLUMN` for any of the
three columns that are missing. Existing data is preserved.

## Package parsing (backend/packages.py)

`parse_package(file_bytes, filename)` → dict or abort(400):

1. Size guard: reject uploads > 20 MB (raw) and archives whose declared
   uncompressed total > 50 MB (zip-bomb guard).
2. `zipfile.is_zipfile` on a BytesIO — reject non-ZIPs
   ("Not a valid .skill package (must be a ZIP archive)").
3. Locate `SKILL.md`: member named `SKILL.md` or `*/SKILL.md` (one directory
   deep). None → 400 ("No SKILL.md found in package"). Two at the same
   shallowest depth → 400 ("Multiple SKILL.md files found").
4. Read and decode as UTF-8; split frontmatter: file must start with `---`,
   frontmatter ends at the next `---` line. Parse with `yaml.safe_load`.
   Missing/invalid frontmatter, or frontmatter without a `name` → 400.
5. Return:
   ```python
   {
     "name": str,            # frontmatter name, stripped
     "description": str,     # frontmatter description or ""
     "content": str,         # markdown body after frontmatter, lstripped
     "bundled_files": [str], # non-directory members, archive-relative,
                             # excluding the SKILL.md itself
   }
   ```

Everything happens in memory — nothing is extracted to disk, so path
traversal (zip-slip) is not a concern. The blob stored is the raw upload.

New dependency: `pyyaml` in `backend/requirements.txt`.

## API

### `POST /api/skills/upload` (login required)

Multipart form: `file` (required), optional `category`, `tags`
(comma-separated string), `status`, `dry_run`.

- `dry_run=1` → parse only, return
  `{name, description, content, bundled_files}` with 200; nothing is created.
- Otherwise: reject duplicate names (400, same message as manual create),
  create the skill (owner = uploader) via the existing `create_skill` path
  semantics, then attach `package_blob`/`package_filename`/`bundled_files` to
  version 1. Audit action `upload`: `Uploaded package '<filename>'`.
  Returns 201 with the skill dict (`my_permission: "edit"`).

### `POST /api/skills/<id>/upload` (login + edit permission)

Multipart form: `file` (required), optional `change_note`.

- Parses the package; **content ← body, description ← frontmatter
  description**. Name, category, tags, status are left untouched (renaming
  stays a deliberate manual edit; the frontmatter name is NOT applied and no
  name-conflict check is needed).
- Creates version N+1 with the package attached, default change note
  `Uploaded package '<filename>'` when none given. Bumps `updated_at`.
  Audit action `upload`. Returns the new version dict.

### `GET /api/skills/<id>/versions/<n>/package` (login + read visibility)

- 404 if skill invisible, version missing, or version has no package.
- Otherwise `send_file` of the blob, `application/zip`, as attachment with
  the original filename.

## Frontend

No new dependencies — the server does all parsing.

**Dashboard:** an "Upload .skill" ghost button next to "New Skill". Opens
`UploadSkillModal`:

1. File input (`accept=".skill,.zip"`). On selection, POST the file with
   `dry_run=1` and render the preview: parsed name, description, first lines
   of content, and the bundled-files list (mono chips).
2. Editable category / tags / status fields (same widgets as SkillFormModal);
   name and description are read-only (they come from the package).
3. "Create skill" POSTs the same file without dry_run, then navigates to the
   new detail page. Server 400s render in the modal banner.

**Skill detail:**

- History tab (edit users): "Upload new version" button → small modal with
  file input + change-note field → POST to `/api/skills/<id>/upload`, reload.
- Version rows with `has_package` show a package chip linking to the
  download endpoint (plain `<a href>` — session cookie authenticates it).
- Header: when the latest version has a package, show a "Download .skill"
  button next to Edit/Delete.

`api/client.js` gains `api.upload(path, formData)` — fetch POST without a
JSON content-type header, same error handling as the JSON helpers.

## Testing

`backend/tests/test_upload.py`, with an in-memory ZIP builder helper
(`make_package(name, description, body, extra_files={})` using
`zipfile.ZipFile(BytesIO(), "w")`). Coverage:

- create via upload: skill fields from frontmatter, v1 has package fields,
  audit `upload` entry, `has_package` in version listing
- SKILL.md at root and one-directory-deep both accepted
- dry_run returns parse result and creates nothing
- rejects: non-zip bytes, zip without SKILL.md, missing frontmatter,
  frontmatter without name, duplicate skill name, oversized upload
- upload new version: content+description updated, name/category/tags/status
  untouched, version N+1, requires edit (403 for read-only user)
- package download: correct bytes + attachment headers; 404 for invisible
  skill (unpermitted user), missing version, and manual (package-less) version
- migration: opening an old-schema DB adds the three columns (covered
  implicitly by app fixtures using `create_all` + the pragma check running)

Existing 42 tests must stay green.

## Out of scope

- Rendering/executing bundled scripts in the UI (list + download only)
- Applying frontmatter `name` on new-version uploads (manual edit instead)
- Exporting manually-authored skills as generated `.skill` archives
- Non-UTF-8 SKILL.md encodings
