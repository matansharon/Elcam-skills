# Deploying the Elcam Skill Registry — llmadmin (Windows Server)

**Audience:** the Claude Code agent running on the **llmadmin** Windows Server.
Follow these steps in order. Each step has a **verify** you must confirm before
moving on. Stop and report if a verify fails.

## What you are deploying

The **Elcam Skill Registry** — a Flask (SQLAlchemy + SQLite) API that also
serves a built React/Vite single-page app. Repo:
`https://github.com/matansharon/Elcam-skills.git` (branch `main`).

**Target end state (chosen for this deployment):**

- **Windows Server**, **internal network only** (no public internet, no TLS).
- Served by **Waitress** (a production WSGI server) — *not* the Flask dev
  server — behind an **NSSM** Windows service that auto-starts on boot and
  auto-restarts on crash.
- Reachable at **`http://llmadmin:<PORT>`** from inside the network
  (default `PORT=5100`).
- Data in a local **SQLite** file (`backend\skills.db`).

> If this ever needs to be public, do **not** just open the firewall — put it
> behind IIS/nginx/Caddy with TLS and enable secure cookies first. That is out
> of scope here (internal-only was chosen).

Assume commands run in **PowerShell**. Replace `C:\apps\Elcam-Skills` below if
you install elsewhere, and keep the path consistent throughout.

---

## Step 1 — Prerequisites

Check each tool; install any that is missing, then re-verify.

```powershell
python --version      # need 3.10+  (if 'python' is missing/wrong, try 'py -3')
node --version        # need 18+
npm --version
git --version
nssm                  # NSSM service manager; prints usage if installed
```

- **Python 3.10+** — https://www.python.org/downloads/windows/ (check "Add to
  PATH"). On this OS use `python` (or `py -3`); do not rely on `python3`.
- **Node.js 18+ LTS** — https://nodejs.org (includes npm).
- **Git** — https://git-scm.com/download/win
- **NSSM** — https://nssm.cc/download (put `nssm.exe` on PATH, e.g. in
  `C:\Windows\System32` or a folder you add to PATH). If you have the
  `nssm-service-manager` skill, you may use it for Step 8 instead of the raw
  commands.

**Verify:** all five commands above print a version / usage without error.

---

## Step 2 — Get the code

```powershell
New-Item -ItemType Directory -Force C:\apps | Out-Null
cd C:\apps
git clone https://github.com/matansharon/Elcam-skills.git Elcam-Skills
cd C:\apps\Elcam-Skills
git checkout main
git pull
```

If the repo is already cloned, just:

```powershell
cd C:\apps\Elcam-Skills
git checkout main
git pull
```

**Verify:** `git log --oneline -1` shows the latest commit, and
`Test-Path .\backend\app.py` and `Test-Path .\frontend\package.json` are both
`True`.

---

## Step 3 — Backend: virtual environment + dependencies

Create a project-local venv named `.venv` and install requirements **plus
Waitress** (Waitress is the production server and is not in requirements.txt).

```powershell
cd C:\apps\Elcam-Skills
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m pip install waitress
```

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m pip show waitress   # prints Waitress metadata
```

---

## Step 4 — Frontend: build the SPA

Flask serves the compiled app from `frontend\dist`. Build it:

```powershell
cd C:\apps\Elcam-Skills\frontend
npm install
npm run build
cd C:\apps\Elcam-Skills
```

**Verify:** `Test-Path .\frontend\dist\index.html` is `True`.

---

## Step 5 — Configuration (`backend\.env`)

`backend\.env` is **git-ignored** (it is not in the clone) and is loaded
automatically at startup. Create it now. **`SECRET_KEY` is mandatory** — the
code default (`dev-secret-change-me`) is public, and leaving it lets anyone
forge login sessions.

Generate a strong secret:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Create `C:\apps\Elcam-Skills\backend\.env` with this content (paste the secret,
choose a strong admin-panel password, pick a free `PORT`):

```ini
# --- required ---
SECRET_KEY=PASTE_THE_GENERATED_HEX_HERE
HOST=0.0.0.0
PORT=5100

# --- activity admin panel at /activity (optional; blank disables it) ---
ADMIN_PANEL_USER=owner
ADMIN_PANEL_PASSWORD=CHOOSE_A_STRONG_PASSWORD
# cap stored activity rows, oldest trimmed past it; blank = keep everything
ACTIVITY_LOG_MAX_ROWS=

# --- optional: "Suggest with AI" feature; blank leaves it disabled ---
ANTHROPIC_API_KEY=
ANALYSIS_MODEL=claude-sonnet-5

# --- optional: override DB location (default: backend\skills.db) ---
# DATABASE_URL=sqlite:///C:/apps/Elcam-Skills/backend/skills.db
```

> Confirm `PORT` is free: `Test-NetConnection -ComputerName localhost -Port 5100`
> should **fail** to connect before deployment. Change `PORT` (here and later)
> if something already uses it.

**Verify:** `Test-Path .\backend\.env` is `True` and `SECRET_KEY` is a long
random value (not `dev-secret-change-me`).

---

## Step 6 — Database and the first admin user

The database schema is created automatically on first startup
(`db.create_all()`), so there is nothing to migrate. But an empty database has
**no users**, and the only built-in seeding script ships **public demo
passwords**. Pick one path:

### Path A — real registry (recommended)

Start empty and create one real admin. Create
`C:\apps\Elcam-Skills\backend\manage_admin.py`:

```python
"""Create the admin user if missing, or reset its password. Run from backend/.

Usage: python manage_admin.py <username> <password> [display_name]
"""
import sys

from app import create_app
from models import db, User


def main():
    if len(sys.argv) < 3:
        print("Usage: python manage_admin.py <username> <password> [display_name]")
        sys.exit(1)
    username, password = sys.argv[1], sys.argv[2]
    display = sys.argv[3] if len(sys.argv) > 3 else username
    app = create_app()  # also creates the schema on a fresh DB
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, display_name=display, role="admin")
            db.session.add(user)
            action = "Created"
        else:
            user.role = "admin"
            action = "Updated"
        user.set_password(password)
        db.session.commit()
        print(f"{action} admin user '{username}'.")


if __name__ == "__main__":
    main()
```

Run it (must run from `backend\` so imports resolve):

```powershell
cd C:\apps\Elcam-Skills\backend
..\.venv\Scripts\python.exe manage_admin.py admin "CHOOSE_A_STRONG_PASSWORD" "Administrator"
cd C:\apps\Elcam-Skills
```

**Verify:** it prints `Created admin user 'admin'.` and
`Test-Path .\backend\skills.db` is `True`.

### Path B — demo/evaluation only

Loads the sample skills, graph, and users — **but with public passwords**
(`admin/admin123`, `dana/dana123`, `yossi/yossi123`). Only use this for a
throwaway demo. `--force` wipes any existing data.

```powershell
cd C:\apps\Elcam-Skills
.\.venv\Scripts\python.exe backend\seed.py --force
```

If you use Path B, immediately harden it: create `manage_admin.py` as in Path A
and reset every seeded account to a strong password:

```powershell
cd C:\apps\Elcam-Skills\backend
..\.venv\Scripts\python.exe manage_admin.py admin "STRONG_PASSWORD_1" "Administrator"
..\.venv\Scripts\python.exe manage_admin.py dana  "STRONG_PASSWORD_2" "Dana Levi"
..\.venv\Scripts\python.exe manage_admin.py yossi "STRONG_PASSWORD_3" "Yossi Cohen"
cd C:\apps\Elcam-Skills
```

---

## Step 7 — Production entrypoint + local smoke test

`python backend\app.py` runs Flask's **dev server with the debugger on** — never
use it in production. Create `C:\apps\Elcam-Skills\backend\serve.py`:

```python
"""Production entrypoint: serve the app with Waitress (no debug server)."""
import os

from waitress import serve

from app import create_app

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5100"))
    serve(create_app(), host=host, port=port, threads=8)
```

Smoke-test it in the foreground (run from `backend\` so imports resolve):

```powershell
cd C:\apps\Elcam-Skills\backend
..\.venv\Scripts\python.exe serve.py
```

In a second PowerShell window:

```powershell
Invoke-RestMethod http://localhost:5100/api/health   # -> status : ok
(Invoke-WebRequest http://localhost:5100/).StatusCode  # -> 200 (the SPA)
```

**Verify:** health returns `ok` and the root returns `200`. Then stop the
foreground process with `Ctrl+C` — the service in Step 8 will run it for real.

---

## Step 8 — Run as a Windows service (NSSM)

This makes the app start on boot and restart on crash. Create a logs folder,
then register the service. (If you have the `nssm-service-manager` skill, use it
with these same values.)

```powershell
New-Item -ItemType Directory -Force C:\apps\Elcam-Skills\logs | Out-Null

nssm install ElcamSkillRegistry "C:\apps\Elcam-Skills\.venv\Scripts\python.exe" "serve.py"
nssm set ElcamSkillRegistry AppDirectory "C:\apps\Elcam-Skills\backend"
nssm set ElcamSkillRegistry AppStdout   "C:\apps\Elcam-Skills\logs\service.out.log"
nssm set ElcamSkillRegistry AppStderr   "C:\apps\Elcam-Skills\logs\service.err.log"
nssm set ElcamSkillRegistry Start SERVICE_AUTO_START
nssm set ElcamSkillRegistry AppExit Default Restart
nssm start ElcamSkillRegistry
```

- `AppDirectory` **must** be the `backend` folder — the app uses top-level
  imports (`from app import ...`) and loads `backend\.env` relative to itself.
- Env vars come from `backend\.env`, so no NSSM env config is needed.

**Verify:**

```powershell
nssm status ElcamSkillRegistry            # -> SERVICE_RUNNING
Invoke-RestMethod http://localhost:5100/api/health   # -> status : ok
```

If it is not running, read `C:\apps\Elcam-Skills\logs\service.err.log`.

---

## Step 9 — Firewall + network reachability

Open the port for inbound traffic on the internal network:

```powershell
New-NetFirewallRule -DisplayName "Elcam Skill Registry 5100" `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5100
```

**Verify:** from **another machine on the network**, browse to
`http://llmadmin:5100/api/health` (substitute the server's real hostname/IP if
`llmadmin` does not resolve; find it with `hostname` / `ipconfig`). You should
get `{"status":"ok"}`.

---

## Step 10 — Final acceptance check

From a workstation on the network, open `http://llmadmin:5100` and confirm:

1. The login screen loads.
2. You can sign in with the admin account you created in Step 6.
3. The **Dashboard** lists skills (empty on Path A; 8 skills on Path B).
4. The **Graph** page renders and is spread/centered.
5. `http://llmadmin:5100/activity` accepts the `ADMIN_PANEL_*` credentials
   from `.env` (if you set them).

Report the URL, the service name (`ElcamSkillRegistry`), and which admin
account exists.

---

## Updating to a new version later

```powershell
nssm stop ElcamSkillRegistry
cd C:\apps\Elcam-Skills
git pull
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend; npm install; npm run build; cd ..
nssm start ElcamSkillRegistry
Invoke-RestMethod http://localhost:5100/api/health
```

The SQLite database is untouched by updates (new columns are added
automatically on startup). `serve.py` and `manage_admin.py` are local files, not
in git, so they survive `git pull`.

## Backups

Back up the database file regularly (and before any risky change). For a
consistent copy, stop the service first:

```powershell
nssm stop ElcamSkillRegistry
Copy-Item C:\apps\Elcam-Skills\backend\skills.db `
  "C:\apps\Elcam-Skills\backups\skills-$(Get-Date -Format yyyyMMdd-HHmmss).db"
nssm start ElcamSkillRegistry
```

(Create `C:\apps\Elcam-Skills\backups` first. Also keep a copy of `backend\.env`
somewhere safe — it holds `SECRET_KEY`; if it changes, all users are logged out.)

## Security checklist (confirm all before handing over)

- [ ] `SECRET_KEY` in `.env` is a strong random value, **not** the default.
- [ ] The app runs via `serve.py` (Waitress) under the service — **not**
      `app.py` (which enables the debugger).
- [ ] No public demo passwords remain (Path A, or Path B with all accounts
      reset).
- [ ] `ADMIN_PANEL_PASSWORD` is strong (or the panel is intentionally disabled
      by leaving the vars blank).
- [ ] `.env` and `skills.db` are not committed to git (they are git-ignored).
- [ ] Firewall exposes the port to the internal network only; the box is not
      reachable from the public internet.

## Troubleshooting

- **`Frontend build not found`** on `/` → run Step 4 (`npm run build`) and
  confirm `frontend\dist\index.html` exists.
- **`ModuleNotFoundError: app` / import errors** → you ran Python from the wrong
  folder. `serve.py`, `seed.py`, and `manage_admin.py` must run with the working
  directory set to `backend\` (the NSSM `AppDirectory` handles this for the
  service).
- **401 / logged out after restart** → `SECRET_KEY` is missing or changing
  between restarts. Set a fixed value in `.env`.
- **Service won't start** → read `logs\service.err.log`; common causes are a
  missing `.env`, a busy `PORT`, or Waitress not installed (`pip show waitress`).
- **Port already in use** → change `PORT` in `.env`, update the firewall rule and
  the verify URLs, then `nssm restart ElcamSkillRegistry`.
- **Reset everything (demo box)** → `nssm stop ElcamSkillRegistry`, delete
  `backend\skills.db`, re-seed or re-bootstrap, `nssm start ElcamSkillRegistry`.
