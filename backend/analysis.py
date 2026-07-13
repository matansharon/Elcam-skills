"""Call Claude to analyze a skill and return sanitized suggestions.

Flask-free on purpose: the Anthropic client is passed in, so the route layer
owns configuration and tests inject a fake. All model output is treated as
untrusted and sanitized before it leaves this module.
"""
from models import RELATIONSHIP_TYPES, STATUSES

MAX_TAGS = 8
MAX_RELATED = 5

TOOL = {
    "name": "record_skill_analysis",
    "description": "Record the structured analysis of a skill.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "A single short category, e.g. 'data-extraction'.",
            },
            "status": {"type": "string", "enum": list(STATUSES)},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-7 short lowercase tags.",
            },
            "related": {
                "type": "array",
                "description": "0-5 related skills chosen ONLY from the provided ids.",
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


class AnalysisError(Exception):
    """Raised when Claude's response can't be turned into an analysis."""


def analyze_skill(client, model, name, description, content, candidates):
    """Return {category, status, tags, related} for a skill.

    `candidates` is a list of {id, name, description, category}; `related`
    entries are constrained to those ids. Raises AnalysisError on a
    malformed response.
    """
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{"role": "user", "content": _prompt(name, description, content, candidates)}],
    )

    tool_input = None
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "tool_use":
            tool_input = block.input
            break
    if not isinstance(tool_input, dict):
        raise AnalysisError("No tool_use block in Claude response")

    return _sanitize(tool_input, {c["id"] for c in candidates})


def _prompt(name, description, content, candidates):
    lines = [
        "You are cataloguing an internal AI 'skill' for a registry.",
        "Analyze the skill below and call record_skill_analysis with:",
        "- category: one short category slug",
        "- status: draft unless the content clearly reads production-ready",
        "- tags: 3-7 short lowercase tags",
        "- related: 0-5 of the candidate skills that genuinely relate, each with",
        "  the best-fitting relationship type. Use ONLY the candidate ids below;",
        "  if none fit, return an empty list.",
        "",
        f"Skill name: {name}",
        f"Description: {description}",
        "",
        "Skill content:",
        content,
        "",
        "Candidate skills (id — name — description):",
    ]
    if candidates:
        for c in candidates:
            lines.append(f"{c['id']} — {c['name']} — {c.get('description', '')}")
    else:
        lines.append("(none)")
    return "\n".join(lines)


def _sanitize(raw, candidate_ids):
    status = raw.get("status")
    if status not in STATUSES:
        status = "draft"
    return {
        "category": str(raw.get("category") or "").strip(),
        "status": status,
        "tags": _clean_tags(raw.get("tags")),
        "related": _clean_related(raw.get("related"), candidate_ids),
    }


def _clean_tags(raw):
    if not isinstance(raw, list):
        return []
    out, seen = [], set()
    for tag in raw:
        text = str(tag).strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= MAX_TAGS:
            break
    return out


def _clean_related(raw, candidate_ids):
    if not isinstance(raw, list):
        return []
    out, seen = [], set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        skill_id = entry.get("skill_id")
        rel_type = entry.get("type")
        if skill_id not in candidate_ids or rel_type not in RELATIONSHIP_TYPES:
            continue
        key = (skill_id, rel_type)
        if key in seen:
            continue
        seen.add(key)
        out.append({"skill_id": skill_id, "type": rel_type})
        if len(out) >= MAX_RELATED:
            break
    return out
