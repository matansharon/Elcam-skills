# AI-Assisted Skill Analysis + Related-Skills Picker — Design

**Date:** 2026-07-13
**Status:** Approved

## Goal

On the skill **create** and **upload** flows, let the user ask Claude to analyze
the skill and pre-fill **category, status, tags, and related skills**, and give
them a **related-skills picker** to choose links from existing skills in the
registry. On save, picked related skills become real typed relationships.

## Scope

- Applies to **create** (`POST /api/skills`) and **upload**
  (`POST /api/skills/upload`) flows only.
- Analysis is **on-demand**: a "✨ Suggest with AI" button, not automatic.
- Related suggestions and the picker are **typed** — each related skill carries
  one of the existing relationship types (`depends_on`, `extends`, `used_with`,
  `replaces`).
- Claude runs **server-side** via the Anthropic SDK (model default
  `claude-sonnet-5`, overridable by env var).

**Out of scope:** AI on the Edit flow (the Links tab already handles
relationships for existing skills); persisting Claude's reasoning; re-analyzing
existing skills; response streaming; any non-English UI.

## Key Decisions

| Decision | Choice |
|---|---|
| AI backend | Real Anthropic API; key from `ANTHROPIC_API_KEY` env |
| Trigger | On-demand "✨ Suggest with AI" button |
| Related richness | Skills **+** relationship type per skill |
| Model | `claude-sonnet-5`, overridable via `ANALYSIS_MODEL` |

## Architecture

Three moving parts:

1. **`analysis.py`** — a Flask-free module that builds the prompt, calls Claude
   with forced tool-use for structured output, and sanitizes the result. The
   Anthropic client is passed in as an argument so tests inject a fake.
2. **`POST /api/skills/analyze`** — a thin route that assembles the candidate
   list (skills visible to the caller), invokes `analysis.py`, and returns
   sanitized suggestions. Creates nothing.
3. **Create-with-related** — the two existing create paths gain an optional
   `related` list; after the skill + v1 are created, each entry becomes a
   `SkillRelationship` in the same transaction.

Nothing about the AI output is trusted: it is sanitized server-side before it
leaves `analysis.py`, and re-validated against the real relationship rules when
links are actually created on save.

## Backend

### Config & dependencies

- `backend/requirements.txt` adds `anthropic>=0.40` and `python-dotenv>=1.0`.
- `backend/config.py`:
  - Loads a `.env` file at import time via `python-dotenv` (`load_dotenv()`),
    so a developer can drop the key in `backend/.env` without exporting it.
  - Exposes on `Config`:
    - `ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")` (may be `None`).
    - `ANALYSIS_MODEL = os.environ.get("ANALYSIS_MODEL", "claude-sonnet-5")`.
- `backend/.env` is added to `.gitignore`. A `backend/.env.example` documents
  the two vars. The key never reaches the frontend.

### `analysis.py`

```python
MAX_TAGS = 8
MAX_RELATED = 5

TOOL = {
    "name": "record_skill_analysis",
    "description": "Record the analysis of a skill.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "status": {"type": "string", "enum": list(STATUSES)},
            "tags": {"type": "array", "items": {"type": "string"}},
            "related": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "skill_id": {"type": "integer"},
                        "type": {"type": "string", "enum": list(RELATIONSHIP_TYPES)},
                        "reason": {"type": "string"},
                    },
                    "required": ["skill_id", "type"],
                },
            },
        },
        "required": ["category", "status", "tags", "related"],
    },
}

def analyze_skill(client, model, name, description, content, candidates):
    """Call Claude for a structured analysis and return a sanitized dict.

    `candidates` is a list of {id, name, description, category} for skills the
    caller may see. Returns {category, status, tags, related:[{skill_id,type}]}.
    Raises AnalysisError on transport/format failure (caller maps to 502).
    """
```

Behavior:
- Builds a system/user prompt containing the skill's `name`, `description`,
  `content`, and a compact rendering of `candidates` (id, name, description).
  Instructs Claude to choose one category, a status (lean `draft` unless the
  content clearly reads production-ready), 3–7 tags, and 0–5 related skills
  **selected only from the provided ids**, each with the best-fitting type.
- Calls `client.messages.create(model=model, max_tokens=..., tools=[TOOL],
  tool_choice={"type": "tool", "name": "record_skill_analysis"}, messages=...)`.
- Extracts the `tool_use` block's `input`. If no tool_use block is present,
  raises `AnalysisError`.
- **Sanitizes** before returning:
  - `status` → keep if in `STATUSES`, else `"draft"`.
  - `category` → stripped string (may be empty).
  - `tags` → strip, drop empties, dedupe (case-insensitive first-wins), cap at
    `MAX_TAGS`.
  - `related` → keep only entries whose `skill_id` is in the candidate id set
    and whose `type` is in `RELATIONSHIP_TYPES`; drop `reason`; dedupe by
    `(skill_id, type)`; cap at `MAX_RELATED`.
- `AnalysisError` is a module-level exception class.

### `POST /api/skills/analyze`

- `@login_required`. Body JSON: `{name?, description?, content}`.
- `content` (or description) must be non-empty, else `400`.
- If `Config.ANTHROPIC_API_KEY` is falsy → `503`
  `{"error": "AI analysis is not configured"}`.
- Builds `candidates` from `visible_skills(current_user)` →
  `[{id, name, description, category}, ...]`.
- Constructs an Anthropic client with the configured key, calls
  `analyze_skill(...)`. On `AnalysisError` or any client exception → `502`
  `{"error": "AI analysis failed"}`.
- On success → `200` with the sanitized suggestion dict.
- The Anthropic client construction is done through a small helper
  (`_anthropic_client()`) so endpoint tests can monkeypatch a fake analyzer /
  client without a network call.

### Create-with-related

Extend `services.py`:

- New helper `attach_related(skill, user, related)`:
  - `related` is a list of `{target_skill_id, type}` (missing/empty → no-op).
  - For each entry: validate `type ∈ RELATIONSHIP_TYPES` (else `400`); resolve
    target via `get_visible_skill_or_404`; reject self-link (`400`); skip if an
    identical `(source, target, type)` already exists; otherwise add a
    `SkillRelationship(source=skill, target, type, created_by=user)` and an
    audit `relationship_added` entry. No commit here — the caller owns the txn.
- `create_skill(user, data)`: after `_snapshot` + create audit, call
  `attach_related(skill, user, data.get("related"))` **before** the existing
  `db.session.commit()`.
- `create_skill_from_package(...)`: add a `related=None` parameter; call
  `attach_related` before its commit.

RBAC note: the caller owns the new skill (source), so edit-on-source is implicit;
targets only need to be visible, matching the existing `create_relationship`
rule.

### Route payload wiring (`skills.py`)

- Manual `POST /api/skills`: pass the full JSON body (already does) — `data`
  now may include `related`.
- `POST /api/skills/upload` (non-dry-run create branch): read a `related` form
  field as a JSON string, parse it (tolerate missing/blank → `None`), pass to
  `create_skill_from_package(..., related=parsed)`.

## Frontend

### `api/client.js`

No change needed beyond existing `post`/`upload` helpers.

### `components/RelatedSkillsPicker.jsx` (new, shared)

- Props: `value` (array of `{target_skill_id, type}`), `onChange`,
  `excludeSkillId?` (unused on create; reserved).
- On mount fetches `GET /api/skills` for the option list.
- Renders one row per entry: a skill `<select>` (options = visible skills not
  already picked), a type `<select>` (the four relationship types), and a ✕
  remove button. A "＋ Add related skill" button appends a blank row.
- Emits changes via `onChange`. Purely controlled; holds no submit logic.

### `components/SuggestButton.jsx` (new, shared)

Implemented as one small shared component (not duplicated inline) so the manual
and upload forms stay in sync.

- Props: `getInput` (returns `{name, description, content}` from the host form),
  `onSuggestions` (receives the sanitized dict), `disabled`.
- A "✨ Suggest with AI" button. On click:
  - Gathers the current `name`, `description`, and `content` from the form
    (upload flow uses `preview.description` / `preview.content`).
  - `POST /api/skills/analyze`; shows a spinner while pending; disabled when
    there is no content to analyze.
  - On success: set category, status, tags (joined), and **merge** suggested
    related rows into the picker value (dedupe against existing rows).
  - On error: inline banner (`.banner-error`) with the server message; the form
    stays fully usable for manual entry.

### `components/SkillFormModal.jsx` (manual create mode)

- In the manual `<form>`, add the "✨ Suggest with AI" button (near the content
  field) and the `RelatedSkillsPicker` (below tags/status), **only when
  `uploadOption` is true** (i.e. the create flow — not Edit).
- Include `related` in the payload built in `submit`.

### `components/UploadSkillForm.jsx`

- After the preview renders, add the "✨ Suggest with AI" button and the
  `RelatedSkillsPicker`.
- Add `related` (JSON-stringified) to the FormData in `submit`.

### `pages/Dashboard.jsx`

- `createSkill` already forwards the payload; `related` rides along in the
  manual path. No structural change beyond passing it through.

### Styling (`styles.css`)

- `.suggest-btn` (accent, sparkle), `.related-picker` rows (flex, aligned
  selects + remove), reusing existing chip/field styling.

## Error Handling

| Situation | Result |
|---|---|
| `ANTHROPIC_API_KEY` unset | `503` "AI analysis is not configured"; button shows banner; manual entry unaffected |
| Claude/network/format error | `502` "AI analysis failed"; banner; manual entry unaffected |
| Empty content on analyze | `400`; button disabled client-side as first guard |
| AI returns bad status/type/id | Silently sanitized server-side; never surfaces to relationship creation |
| Related target invisible/self/dup at save | Existing relationship validation (`400` / skip dup) |

The feature is strictly additive: with no key, the app behaves exactly as today
plus a button that reports it's not configured.

## Testing (pytest, no live API)

**`analysis.py` unit tests** — inject a fake client returning canned tool-use:
- happy path returns expected sanitized shape
- invalid `status` clamped to `draft`
- invalid relationship `type` entry dropped
- unknown / non-candidate `skill_id` dropped
- duplicate related entries deduped; tags deduped and capped at `MAX_TAGS`
- missing tool_use block → `AnalysisError`

**Endpoint tests** (`test_analyze.py`, mocked analyzer):
- `200` returns suggestions for a logged-in user
- `503` when key unset
- `401` unauthenticated
- candidate list passed to analyzer respects RBAC (read-only user sees only
  their visible skills)

**Create-with-related tests** (extend `test_skills.py` / `test_upload.py`):
- manual create with `related` creates the relationships (correct type +
  direction) and audit entries
- package create with `related` does the same
- invalid `type` → `400`; invisible target → `404`/`400`; self-link → `400`
- omitted/empty `related` → skill created, no relationships (back-compat: all
  existing create tests still pass unchanged)

## Data Model

No schema changes. `SkillRelationship` already supports everything needed; the
feature only adds a new *way* to create rows plus a stateless analysis endpoint.
