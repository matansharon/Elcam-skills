"""Parse uploaded .skill packages.

A .skill file is a ZIP archive containing a SKILL.md — YAML frontmatter
(name, description) followed by a markdown body — plus optional bundled
resources. Everything is read in memory; nothing is extracted to disk.
"""
import io
import zipfile

import yaml
from flask import abort

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


def parse_package(file_bytes):
    """Validate a .skill archive and return its parsed pieces.

    Returns {"name", "description", "content", "bundled_files"};
    aborts with 400 on any invalid input.
    """
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        abort(400, description="Package too large (max 20 MB)")

    buf = io.BytesIO(file_bytes)
    if not zipfile.is_zipfile(buf):
        abort(400, description="Not a valid .skill package (must be a ZIP archive)")

    with zipfile.ZipFile(buf) as zf:
        if sum(i.file_size for i in zf.infolist()) > MAX_UNCOMPRESSED_BYTES:
            abort(400, description="Package too large when uncompressed (max 50 MB)")

        members = [i.filename for i in zf.infolist() if not i.is_dir()]
        skill_md = _find_skill_md(members)
        try:
            text = zf.read(skill_md).decode("utf-8")
        except UnicodeDecodeError:
            abort(400, description="SKILL.md is not valid UTF-8")

    meta, body = _split_frontmatter(text)
    name = str(meta.get("name") or "").strip()
    if not name:
        abort(400, description="SKILL.md frontmatter must include a name")

    return {
        "name": name,
        "description": str(meta.get("description") or "").strip(),
        "content": body,
        "bundled_files": [m for m in members if m != skill_md],
    }


def _find_skill_md(members):
    """SKILL.md may sit at the archive root or one directory deep."""
    candidates = [
        m for m in members
        if m == "SKILL.md" or (m.count("/") == 1 and m.endswith("/SKILL.md"))
    ]
    if not candidates:
        abort(400, description="No SKILL.md found in package")
    shallowest_depth = min(m.count("/") for m in candidates)
    shallowest = [m for m in candidates if m.count("/") == shallowest_depth]
    if len(shallowest) > 1:
        abort(400, description="Multiple SKILL.md files found in package")
    return shallowest[0]


def _split_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        abort(400, description="SKILL.md must start with YAML frontmatter")
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            try:
                meta = yaml.safe_load("\n".join(lines[1:idx]))
            except yaml.YAMLError:
                abort(400, description="Invalid YAML frontmatter in SKILL.md")
            if not isinstance(meta, dict):
                abort(400, description="Invalid YAML frontmatter in SKILL.md")
            body = "\n".join(lines[idx + 1:]).lstrip("\n")
            return meta, body
    abort(400, description="SKILL.md frontmatter is not closed with ---")
