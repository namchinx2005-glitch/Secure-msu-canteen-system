@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)

if not exist ".venv\Scripts\pip.exe" (
    ".venv\Scripts\python.exe" -m ensurepip --upgrade --default-pip
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" app.py
pause
