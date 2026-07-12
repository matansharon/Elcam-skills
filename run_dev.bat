@echo off
rem Start the Skill Registry in development mode (two processes).
start "Skill Registry Backend" cmd /k ""%~dp0.venv\Scripts\python.exe" "%~dp0backend\app.py""
start "Skill Registry Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
echo Backend:  http://localhost:5000
echo Frontend: http://localhost:5173
