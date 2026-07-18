"""Seed the Skill Registry with demo users, skills, versions, relationships,
and permissions so the app is demonstrable immediately.

Usage:
    python backend/seed.py           # refuses if data already exists
    python backend/seed.py --force   # drop everything and reseed
"""
import argparse
import sys

from app import create_app
from models import (
    Favorite, Folder, SkillFolder, SkillPermission, SkillRelationship, User, db,
)
from services import create_skill, log_action, update_skill


def make_users():
    users = {}
    for username, password, display, role in [
        ("admin", "admin123", "Admin", "admin"),
        ("dana", "dana123", "Dana Levi", "user"),
        ("yossi", "yossi123", "Yossi Cohen", "user"),
    ]:
        user = User(username=username, display_name=display, role=role)
        user.set_password(password)
        db.session.add(user)
        users[username] = user
    db.session.commit()
    return users


SKILLS = [
    {
        "key": "summarizer",
        "owner": "admin",
        "name": "Document Summarizer",
        "description": "Summarizes long engineering and QA documents into short briefs.",
        "category": "document-processing",
        "tags": ["summarization", "documents"],
        "status": "active",
        "versions": [
            ("# Document Summarizer\n\nPaste a document and receive a 5-bullet "
             "executive brief.\n\n## Instructions\n- Keep bullets under 20 words\n"
             "- Preserve numeric values exactly", "Initial version"),
            ("# Document Summarizer\n\nPaste a document and receive a 5-bullet "
             "executive brief plus a risk callout.\n\n## Instructions\n- Keep bullets "
             "under 20 words\n- Preserve numeric values exactly\n- Flag any open "
             "risks in a final **Risks** section", "Added risk callout section"),
        ],
    },
    {
        "key": "pdf_tables",
        "owner": "admin",
        "name": "PDF Table Extractor",
        "description": "Extracts tables from scanned PDF reports into Excel-ready data.",
        "category": "data-extraction",
        "tags": ["pdf", "tables", "excel"],
        "status": "active",
        "versions": [
            ("# PDF Table Extractor\n\nExtracts all tables from a PDF.\n\n## Output\n"
             "CSV per table.", "Initial version"),
            ("# PDF Table Extractor\n\nExtracts all tables from a PDF, including "
             "rotated pages.\n\n## Output\nCSV per table with a source-page column.",
             "Handle rotated pages, add source-page column"),
            ("# PDF Table Extractor\n\nExtracts all tables from a PDF, including "
             "rotated pages and merged cells.\n\n## Output\nCSV per table with a "
             "source-page column.\n\n## Limitations\nHandwritten tables are not "
             "supported.", "Merged-cell support and documented limitations"),
        ],
    },
    {
        "key": "coc_report",
        "owner": "admin",
        "name": "COC Report Generator",
        "description": "Builds Certificate of Conformance reports from batch records.",
        "category": "reporting",
        "tags": ["coc", "quality", "reports"],
        "status": "active",
        "versions": [
            ("# COC Report Generator\n\nGenerates a COC draft from batch data.\n\n"
             "## Inputs\nBatch number, product code.", "Initial version"),
            ("# COC Report Generator\n\nGenerates a COC draft from batch data with "
             "automatic spec lookup.\n\n## Inputs\nBatch number, product code.\n\n"
             "## Validation\nCross-checks specs against the PLM record.",
             "Added spec cross-check"),
        ],
    },
    {
        "key": "regulation",
        "owner": "admin",
        "name": "Regulation Watcher",
        "description": "Tracks regulatory updates and maps them to affected products.",
        "category": "document-processing",
        "tags": ["regulatory", "compliance"],
        "status": "draft",
        "versions": [
            ("# Regulation Watcher\n\nMonitors published regulatory changes and "
             "produces an impact list.\n\n## Scope\nEU MDR, FDA 21 CFR.",
             "Initial version"),
        ],
    },
    {
        "key": "jira_triage",
        "owner": "dana",
        "name": "Jira Ticket Triage",
        "description": "Classifies incoming Jira tickets and suggests owners and priority.",
        "category": "integration",
        "tags": ["jira", "triage", "automation"],
        "status": "active",
        "versions": [
            ("# Jira Ticket Triage\n\nReads a ticket and proposes component, owner, "
             "and priority.\n\n## Rules\nUse the team routing table.",
             "Initial version"),
            ("# Jira Ticket Triage\n\nReads a ticket and proposes component, owner, "
             "priority, and duplicates.\n\n## Rules\nUse the team routing table. "
             "Search open tickets for near-duplicates before assigning.",
             "Duplicate detection"),
        ],
    },
    {
        "key": "meeting_prep",
        "owner": "dana",
        "name": "Meeting Prep Assistant",
        "description": "Prepares one-on-one meeting briefs from calendar and task data.",
        "category": "reporting",
        "tags": ["meetings", "productivity"],
        "status": "active",
        "versions": [
            ("# Meeting Prep Assistant\n\nBuilds a one-page brief before each "
             "meeting.\n\n## Sections\nOpen actions, last summary, suggested topics.",
             "Initial version"),
            ("# Meeting Prep Assistant\n\nBuilds a one-page brief before each "
             "meeting.\n\n## Sections\nOpen actions, last summary, suggested topics, "
             "blockers raised since last time.", "Added blockers section"),
        ],
    },
    {
        "key": "stability",
        "owner": "admin",
        "name": "Stability Report Analyzer",
        "description": "Parses stability study reports and flags out-of-trend results.",
        "category": "data-extraction",
        "tags": ["stability", "quality", "analysis"],
        "status": "active",
        "versions": [
            ("# Stability Report Analyzer\n\nExtracts assay results per time point "
             "and flags out-of-trend values.\n\n## Output\nTrend table plus flags.",
             "Initial version"),
            ("# Stability Report Analyzer\n\nExtracts assay results per time point "
             "and flags out-of-trend values with severity levels.\n\n## Output\n"
             "Trend table plus flags (minor/major).", "Severity levels for flags"),
        ],
    },
    {
        "key": "email_classifier",
        "owner": "admin",
        "name": "Legacy Email Classifier",
        "description": "Routes incoming shared-mailbox email to the right team queue.",
        "category": "integration",
        "tags": ["email", "routing"],
        "status": "deprecated",
        "versions": [
            ("# Legacy Email Classifier\n\nClassifies shared-mailbox email into team "
             "queues.\n\n## Note\nSuperseded by Jira Ticket Triage.",
             "Initial version"),
        ],
    },
]

RELATIONSHIPS = [
    # (source key, target key, type)
    ("coc_report", "pdf_tables", "depends_on"),
    ("stability", "pdf_tables", "depends_on"),
    ("meeting_prep", "summarizer", "depends_on"),
    ("regulation", "summarizer", "extends"),
    ("stability", "summarizer", "used_with"),
    ("jira_triage", "email_classifier", "replaces"),
    ("coc_report", "regulation", "used_with"),
    ("meeting_prep", "jira_triage", "used_with"),
    ("regulation", "stability", "used_with"),
    ("jira_triage", "summarizer", "depends_on"),
]

PERMISSIONS = [
    # (username, skill key, level)
    ("dana", "summarizer", "edit"),
    ("dana", "pdf_tables", "edit"),
    ("dana", "stability", "edit"),
    ("dana", "coc_report", "read"),
    ("dana", "regulation", "read"),
    ("yossi", "summarizer", "read"),
    ("yossi", "pdf_tables", "read"),
    ("yossi", "meeting_prep", "read"),
    # yossi has no access to: coc_report, regulation, jira_triage,
    # stability, email_classifier
]


def make_skills(users):
    skills = {}
    for spec in SKILLS:
        owner = users[spec["owner"]]
        first_content, _ = spec["versions"][0]
        skill = create_skill(owner, {
            "name": spec["name"],
            "description": spec["description"],
            "category": spec["category"],
            "tags": spec["tags"],
            "status": spec["status"],
            "content": first_content,
        })
        for content, note in spec["versions"][1:]:
            update_skill(owner, skill, {"content": content, "change_note": note})
        skills[spec["key"]] = skill
    return skills


def make_relationships(users, skills):
    for source_key, target_key, rel_type in RELATIONSHIPS:
        source, target = skills[source_key], skills[target_key]
        db.session.add(SkillRelationship(
            source_skill_id=source.id,
            target_skill_id=target.id,
            type=rel_type,
            created_by=users["admin"].id,
        ))
        log_action(source.id, users["admin"].id, "relationship_added",
                   f"{source.name} {rel_type} {target.name}")
    db.session.commit()


def make_permissions(users, skills):
    for username, skill_key, level in PERMISSIONS:
        user, skill = users[username], skills[skill_key]
        db.session.add(SkillPermission(
            user_id=user.id, skill_id=skill.id, level=level,
        ))
        log_action(skill.id, users["admin"].id, "permission_set",
                   f"Set {user.display_name} to {level}")
    db.session.commit()


# (folder key, display name, parent key or None)
FOLDERS = [
    ("processing", "Document Processing", None),
    ("extraction", "Data Extraction", None),
    ("quality", "Quality & Reporting", None),
    ("quality_coc", "COC", "quality"),
]

# (folder key, skill key) memberships
FOLDER_SKILLS = [
    ("processing", "summarizer"),
    ("processing", "regulation"),
    ("extraction", "pdf_tables"),
    ("extraction", "stability"),
    ("quality", "coc_report"),
    ("quality_coc", "coc_report"),   # multi-folder membership demo
]

# (username, skill key) favorites
FAVORITES = [
    ("dana", "summarizer"),
    ("dana", "meeting_prep"),
    ("yossi", "pdf_tables"),
]


def make_folders(users, skills):
    folders = {}
    for key, name, parent_key in FOLDERS:
        parent_id = folders[parent_key].id if parent_key else None
        folder = Folder(name=name, parent_id=parent_id, created_by=users["admin"].id)
        db.session.add(folder)
        db.session.flush()  # assign id for children/memberships
        folders[key] = folder
    for folder_key, skill_key in FOLDER_SKILLS:
        db.session.add(SkillFolder(
            skill_id=skills[skill_key].id, folder_id=folders[folder_key].id,
        ))
    db.session.commit()
    return folders


def make_favorites(users, skills):
    for username, skill_key in FAVORITES:
        db.session.add(Favorite(
            user_id=users[username].id, skill_id=skills[skill_key].id,
        ))
    db.session.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="drop all existing data and reseed")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if User.query.first() is not None:
            if not args.force:
                print("Database already contains data. Use --force to reseed.")
                sys.exit(1)
            db.drop_all()
            db.create_all()

        users = make_users()
        skills = make_skills(users)
        make_relationships(users, skills)
        make_permissions(users, skills)
        make_folders(users, skills)
        make_favorites(users, skills)

        print(f"Seeded {len(users)} users, {len(skills)} skills, "
              f"{len(RELATIONSHIPS)} relationships, {len(PERMISSIONS)} permissions, "
              f"{len(FOLDERS)} folders, {len(FAVORITES)} favorites.")
        print("Demo logins: admin/admin123, dana/dana123, yossi/yossi123")


if __name__ == "__main__":
    main()
