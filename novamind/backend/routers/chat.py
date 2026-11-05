"""
routers/chat.py  -  the main endpoint:  POST /api/chat

WHY THIS FILE EXISTS
    This file is the CONDUCTOR. For every message it:
        1. classifies the question            (services/query_router.py)
        2. picks a source: documents / web / nothing
        3. builds the prompt                  (services/rag_service.py)
        4. streams the LLM answer to the browser (services/ollama_client.py)

STREAMING FORMAT  (Server-Sent Events, "SSE")
    The server keeps the HTTP connection open and sends small messages:

        event: status
        data: {"text": "Searching your documents..."}

        event: sources
        data: {"sources": [...]}

        event: token
        data: {"text": "Hello"}          <- repeated many times

        event: done
        data: {}

    A blank line ends each message. The browser (frontend/app.js) reads them
    as they arrive, so the answer appears word by word.
"""

import json
from typing import Dict, Iterator, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from services import ollama_client, rag_service, vector_store
from services.ollama_client import OllamaError
from services.query_router import classify
from services.web_search import web_search

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    mode: str = "auto"                      # "auto" | "docs" | "web"
    history: List[Dict[str, str]] = []      # earlier turns: [{"role","content"}]


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def run_chat(req: ChatRequest) -> Iterator[str]:
    """Generator: every `yield` is sent to the browser immediately."""
    question = req.message.strip()
    try:
        intent = classify(question)
        has_docs = vector_store.count() > 0

        # ------------------------------------------------------------------
        # STEP 1 - choose the first route
        # ------------------------------------------------------------------
        if req.mode == "docs":
            if not has_docs:
                yield sse("token", {"text": "No documents uploaded yet. Add a PDF or text file first."})
                yield sse("done", {})
                return
            route = "docs_strict"            # documents ONLY, never the internet
        elif req.mode == "web":
            route = "web"
        else:                                # AUTO mode - decide from the question
            if intent == "casual":
                route = "none"
            elif intent == "web" or not has_docs:
                route = "web"
            else:
                route = "docs_try"           # try documents, fall back to web

        context_blocks: List[str] = []
        sources: List[dict] = []
        context_kind = "none"

        # ------------------------------------------------------------------
        # STEP 2 - retrieve from documents
        # ------------------------------------------------------------------
        if route in ("docs_strict", "docs_try"):
            yield sse("status", {"text": "Searching your documents..."})

            if intent == "summary":
                results = rag_service.spread_retrieve()          # whole-document sampling
            else:
                found = rag_service.similarity_retrieve(question)
                # IMPORTANT: keep only chunks that pass the similarity threshold
                results = [c for c in found if c["score"] >= settings.SIMILARITY_THRESHOLD]

            if results:
                context_kind = "docs"
                for c in results:
                    context_blocks.append(f"[{c['source']}, page {c['page']}]\n{c['text']}")
                    sources.append(
                        {"type": "doc", "title": f"{c['source']} (page {c['page']})",
                         "score": c["score"], "snippet": c["text"][:160]}
                    )
            elif route == "docs_strict":
                # Anti-hallucination: in Docs mode we refuse instead of guessing.
                yield sse("token", {"text": "I could not find that in your documents."})
                yield sse("done", {})
                return
            else:
                route = "web"                # auto mode: documents had nothing -> use the web

        # ------------------------------------------------------------------
        # STEP 3 - web search (if chosen or fallen back to)
        # ------------------------------------------------------------------
        if route == "web":
            yield sse("status", {"text": "Searching the web..."})
            hits = web_search(question)
            if hits:
                context_kind = "web"
                for h in hits:
                    context_blocks.append(f"[{h['title']}] ({h['url']})\n{h['snippet']}")
                    sources.append({"type": "web", "title": h["title"], "url": h["url"],
                                    "snippet": h["snippet"][:160]})
            elif req.mode == "web":
                yield sse("token", {"text": "Web search returned nothing (offline or rate-limited). Try again in a moment."})
                yield sse("done", {})
                return
            # Auto mode with no web results: continue as a plain chat.

        if sources:
            yield sse("sources", {"sources": sources})

        # ------------------------------------------------------------------
        # STEP 4 - ask the LLM and stream its answer
        # ------------------------------------------------------------------
        yield sse("status", {"text": "Thinking..."})
        messages = rag_service.build_messages(question, req.history, context_blocks, context_kind)
        for piece in ollama_client.chat_stream(messages):
            yield sse("token", {"text": piece})
        yield sse("done", {})

    except OllamaError as exc:
        yield sse("error", {"text": str(exc)})
    except Exception as exc:                  # never let the stream die silently
        yield sse("error", {"text": f"Unexpected error: {exc}"})


@router.post("/chat")
def chat(req: ChatRequest):
    return StreamingResponse(
        run_chat(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # stops reverse proxies from buffering the stream
        },
    )
