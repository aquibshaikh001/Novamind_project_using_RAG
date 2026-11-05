"""
main.py  -  the entry point. `uvicorn main:app` starts this file.

WHY THIS FILE EXISTS
    It creates the FastAPI application, plugs in all routers (the API) and
    also serves the web page from ../frontend. Because the SAME server
    delivers both the page and the API, you only run ONE command and there
    are no cross-origin (CORS) problems.

IMPORTANT: the static-files line must stay LAST. It matches every URL
that is not an API route; if it came first it would hide the API.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import settings
from routers import chat, documents, system, voice

app = FastAPI(
    title="NovaMind",
    description="Private document & voice assistant (RAG)",
    version="1.0.0",
)

# Plug in the API routes
app.include_router(system.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(voice.router)

# Serve the web interface (index.html, style.css, app.js) at  http://127.0.0.1:8000/
app.mount("/", StaticFiles(directory=str(settings.FRONTEND_DIR), html=True), name="frontend")
