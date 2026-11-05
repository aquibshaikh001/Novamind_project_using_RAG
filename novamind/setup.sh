#!/usr/bin/env bash
# setup.sh - ONE-TIME installation for macOS / Linux  (run:  bash setup.sh)
set -e
cd "$(dirname "$0")/backend"
[ -f .env ] || cp ../.env.example .env
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo
echo "Setup finished. Next:  ollama pull llama3.2:3b && ollama pull nomic-embed-text"
echo "Then run:  bash start.sh"
