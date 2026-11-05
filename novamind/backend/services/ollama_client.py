"""
services/ollama_client.py  -  the ONLY file that talks to Ollama.

WHY THIS FILE EXISTS
    Ollama is the program that runs the AI models on your own computer.
    It offers a small HTTP API on http://127.0.0.1:11434.
    Keeping all those HTTP calls here means the rest of the project never
    needs to know how Ollama works (clean separation of concerns).

THREE JOBS
    1. embed()        text  -> list of numbers (a "vector") that captures meaning
    2. chat_stream()  messages -> answer, produced token-by-token
    3. list_models()  which models are installed
"""

import json
from typing import Iterator, List

import httpx

from config import settings


class OllamaError(Exception):
    """Raised when Ollama is not reachable or returns an error.
    The chat router catches it and shows a friendly message in the UI."""


def is_running() -> bool:
    """Return True if the Ollama server answers. Used by the health check."""
    try:
        r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> List[str]:
    """Names of all models downloaded in Ollama, e.g. ['llama3.2:3b', ...]."""
    try:
        r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def embed(texts: List[str]) -> List[List[float]]:
    """
    Convert a list of texts into a list of embedding vectors.

    HOW IT WORKS
        An embedding model reads text and outputs e.g. 768 numbers.
        Texts with similar MEANING get similar numbers. That is what lets us
        later find "the chunk that answers the question".

    IMPORTANT: the SAME embedding model must be used for ingestion and for
    questions. If you change EMBEDDING_MODEL, delete backend/chroma_db and
    upload your documents again.
    """
    if not texts:
        return []
    try:
        r = httpx.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={"model": settings.EMBEDDING_MODEL, "input": texts},
            timeout=120,
        )
        if r.status_code == 404:
            raise OllamaError(
                f"Embedding model '{settings.EMBEDDING_MODEL}' is not installed. "
                f"Run:  ollama pull {settings.EMBEDDING_MODEL}"
            )
        r.raise_for_status()
        return r.json()["embeddings"]
    except OllamaError:
        raise
    except httpx.ConnectError:
        raise OllamaError("Cannot reach Ollama. Start it with:  ollama serve")
    except Exception as exc:
        raise OllamaError(f"Embedding failed: {exc}")


def chat_stream(messages: List[dict]) -> Iterator[str]:
    """
    Send a conversation to the LLM and YIELD the answer piece by piece.

    `messages` looks like:
        [{"role": "system", "content": "..."},
         {"role": "user",   "content": "..."}]

    Ollama replies with one JSON object per line, for example:
        {"message": {"content": "Hel"}, "done": false}
        {"message": {"content": "lo"},  "done": false}
        {"done": true}
    We read line by line and yield each text piece immediately - this is
    what makes the answer appear word-by-word in the browser.
    """
    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "stream": True,
        # num_ctx = how many tokens the model can "see" at once.
        "options": {"num_ctx": settings.OLLAMA_NUM_CTX},
    }
    try:
        # timeout=None: a slow computer may need a long time for the first token.
        with httpx.stream(
            "POST", f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload, timeout=None
        ) as response:
            if response.status_code == 404:
                raise OllamaError(
                    f"Model '{settings.LLM_MODEL}' is not installed. "
                    f"Run:  ollama pull {settings.LLM_MODEL}"
                )
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                piece = data.get("message", {}).get("content", "")
                if piece:
                    yield piece
                if data.get("done"):
                    break
    except OllamaError:
        raise
    except httpx.ConnectError:
        raise OllamaError("Cannot reach Ollama. Start it with:  ollama serve")
    except Exception as exc:
        raise OllamaError(f"Chat failed: {exc}")
