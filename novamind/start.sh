#!/usr/bin/env bash
# start.sh - starts NovaMind on macOS / Linux  (run:  bash start.sh)
cd "$(dirname "$0")/backend"
source .venv/bin/activate
echo "Open http://127.0.0.1:8000 in your browser"
python -m uvicorn main:app --host 127.0.0.1 --port 8000
