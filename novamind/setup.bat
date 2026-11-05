@echo off
REM ===================================================================
REM setup.bat - ONE-TIME installation (Windows). Run it once.
REM   1. creates backend\.env from the template
REM   2. creates a private Python environment (.venv)
REM   3. installs all Python packages
REM ===================================================================
cd /d "%~dp0backend"

if not exist .env copy ..\.env.example .env

if not exist .venv (
    echo Creating Python virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ==================================================
echo  Setup finished. Next:
echo    ollama pull llama3.2:3b
echo    ollama pull nomic-embed-text
echo    then double-click start.bat
echo ==================================================
pause
