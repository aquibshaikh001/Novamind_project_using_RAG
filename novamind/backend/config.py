"""
config.py  -  central place for ALL settings.

WHY THIS FILE EXISTS
    Every other file imports `settings` from here instead of reading
    environment variables on its own. If you want to change a model name,
    a threshold or a folder, you change it in ONE place (the .env file).

IMPORTANT POINTS
    * Values come from  backend/.env  (copied from .env.example).
    * If a value is missing in .env, the default after the comma is used.
    * `LLM_MODEL` can be changed while the app runs (see routers/system.py),
      so `settings` is a normal mutable object.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Folder that contains this file  ->  <project>/backend
BASE_DIR = Path(__file__).resolve().parent

# Load key=value pairs from backend/.env into os.environ.
# If the file does not exist nothing happens (defaults are used).
load_dotenv(BASE_DIR / ".env")


def _to_bool(value: str) -> bool:
    """Turn text such as 'true', '1', 'yes' into a real True/False."""
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    """Holds every configurable value of NovaMind."""

    def __init__(self) -> None:
        # ---------- Ollama ----------
        self.OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.2:3b")
        self.EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        self.OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

        # ---------- Retrieval ----------
        self.SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.35"))
        self.CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "800"))
        self.CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))

        # ---------- Storage ----------
        self.DATA_DIR: Path = BASE_DIR / "data"            # uploaded files
        self.CHROMA_DIR: Path = BASE_DIR / "chroma_db"     # vector database files
        self.COLLECTION_NAME: str = "novamind_docs"
        self.FRONTEND_DIR: Path = BASE_DIR.parent / "frontend"
        self.MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "20"))

        # ---------- Voice ----------
        self.STT_ENABLED: bool = _to_bool(os.getenv("STT_ENABLED", "false"))
        self.WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
        self.TTS_VOICE: str = os.getenv("TTS_VOICE", "en-IN-NeerjaNeural")

        # Make sure the folders exist so later code never fails on a missing path.
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.CHROMA_DIR.mkdir(parents=True, exist_ok=True)


# ONE shared instance - every file does:  from config import settings
settings = Settings()
