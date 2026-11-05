"""
services/rag_service.py  -  the "brain" of RAG: retrieval + prompt building.

RAG = Retrieval Augmented Generation.
    1. RETRIEVE the most useful text from your documents.
    2. AUGMENT the prompt by pasting that text in front of the question.
    3. GENERATE the answer with the LLM (done in routers/chat.py).

This file contains two retrieval strategies and the prompt builders.
"""

import re
from typing import Dict, List

from config import settings
from services import ollama_client, vector_store


# ----------------------------------------------------------------------
# Strategy 1: SIMILARITY retrieval  (for specific questions)
# ----------------------------------------------------------------------
def similarity_retrieve(question: str, k: int = 4) -> List[Dict]:
    """
    Embed the question and return the k closest chunks.
    Every chunk has a `score` between 0 and 1 (higher = more relevant).
    """
    query_vector = ollama_client.embed([question])[0]
    return vector_store.search(query_vector, k=k)


# ----------------------------------------------------------------------
# Strategy 2: SPREAD retrieval  (for "summarize this document")
# ----------------------------------------------------------------------
def looks_like_references(text: str) -> bool:
    """
    Heuristic: is this chunk a bibliography / reference list?
    Reference lists are useless for a summary, so we skip them.
    """
    lowered = text.lower().strip()
    if lowered.startswith(("references", "bibliography")):
        return True
    numbered = len(re.findall(r"\[\d+\]", text))            # [1] [2] ...
    markers = sum(lowered.count(w) for w in ("et al", "arxiv", "doi:", "proceedings"))
    return numbered >= 4 or markers >= 4


def spread_retrieve(max_chunks: int = 8) -> List[Dict]:
    """
    Pick chunks spread EVENLY over the whole document(s).

    WHY: similarity search for "summarize" would return 4 chunks that all
    sit in the same place. A good summary needs the beginning (abstract /
    intro), the middle and the end (conclusion).

    HOW: drop reference chunks, then take `max_chunks` positions evenly
    spaced from the first chunk to the last chunk.
    """
    chunks = [c for c in vector_store.get_all_chunks() if not looks_like_references(c["text"])]
    if len(chunks) <= max_chunks:
        return chunks

    last = len(chunks) - 1
    # evenly spaced indexes, always including 0 (start) and last (end)
    indexes = sorted({round(i * last / (max_chunks - 1)) for i in range(max_chunks)})
    picked = [chunks[i] for i in indexes]
    for chunk in picked:
        chunk["score"] = 1.0        # not a similarity result; keeps UI format the same
    return picked


# ----------------------------------------------------------------------
# Prompt building
# ----------------------------------------------------------------------
SYSTEM_BASE = (
    "You are NovaMind, a friendly and precise personal assistant. "
    "Answer clearly in simple language."
)


def build_messages(
    question: str,
    history: List[Dict],
    context_blocks: List[str],
    context_kind: str,
) -> List[dict]:
    """
    Build the message list that is sent to the LLM.

    context_kind:
        'docs' -> answer ONLY from the supplied document excerpts
        'web'  -> answer from the supplied web results
        'none' -> normal conversation, no extra context
    """
    if context_kind == "docs":
        system = (
            SYSTEM_BASE + " Use ONLY the document excerpts below to answer. "
            "If the excerpts do not contain the answer, say exactly: "
            "'I could not find that in your documents.' Never invent facts."
        )
    elif context_kind == "web":
        system = (
            SYSTEM_BASE + " Use the web search results below to answer. "
            "Mention the source titles you used. If the results do not help, say so."
        )
    else:
        system = SYSTEM_BASE

    messages: List[dict] = [{"role": "system", "content": system}]

    # Keep only the last 6 turns, otherwise the context window overflows.
    for turn in history[-6:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})

    if context_blocks:
        # IMPORTANT: cap the context size so we never exceed num_ctx.
        context = "\n\n".join(context_blocks)[:6000]
        user_content = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    else:
        user_content = question

    messages.append({"role": "user", "content": user_content})
    return messages
