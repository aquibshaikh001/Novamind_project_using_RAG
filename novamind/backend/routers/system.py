"""
routers/system.py  -  health check, model list/switch and hardware advice.

WHY THIS FILE EXISTS
    The browser needs to know: "Is Ollama running? Which models can I pick?
    How many documents are loaded?" These small endpoints answer that so the
    UI can show a green/red status light and a model dropdown.
"""

import shutil
import subprocess
import platform
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from services import ollama_client, vector_store

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> Dict:
    """Status summary used by the UI header."""
    return {
        "ollama_running": ollama_client.is_running(),
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "chunks_stored": vector_store.count(),
        "stt_enabled": settings.STT_ENABLED,
    }


@router.get("/models")
def models() -> Dict:
    """Installed Ollama models + the one currently selected."""
    return {"installed": ollama_client.list_models(), "active": settings.LLM_MODEL}


class ModelChoice(BaseModel):
    llm_model: str


@router.post("/models/select")
def select_model(choice: ModelChoice) -> Dict:
    """
    Switch the chat model WITHOUT restarting the server.
    Only models that are installed in Ollama are accepted.
    (Embedding model is NOT switchable: stored vectors depend on it.)
    """
    if choice.llm_model not in ollama_client.list_models():
        raise HTTPException(status_code=400, detail="That model is not installed in Ollama.")
    settings.LLM_MODEL = choice.llm_model
    return {"active": settings.LLM_MODEL}


@router.get("/hardware")
def hardware() -> Dict:
    """Detect GPU memory (NVIDIA only) and recommend a model size."""
    gpu_name, vram_gb = None, 0.0
    if shutil.which("nvidia-smi"):           # only present if an NVIDIA driver is installed
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip().splitlines()[0]
            name, mem = out.split(",")
            gpu_name, vram_gb = name.strip(), round(float(mem) / 1024, 1)
        except Exception:
            pass

    if vram_gb >= 12:
        recommended = "qwen2.5:14b"
    elif vram_gb >= 6:
        recommended = "qwen2.5:7b"
    else:
        recommended = "llama3.2:3b"       # safe choice for CPU-only machines

    return {
        "os": platform.system(),
        "gpu": gpu_name or "No NVIDIA GPU detected (CPU mode)",
        "vram_gb": vram_gb,
        "recommended_model": recommended,
        "pull_command": f"ollama pull {recommended}",
    }
