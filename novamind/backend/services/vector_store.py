"""
services/vector_store.py  -  everything about ChromaDB (our vector database).

WHY THIS FILE EXISTS
    A vector database stores (text chunk, its embedding, extra info) and can
    answer: "which stored chunks are closest in meaning to this question?"
    ChromaDB keeps its files on disk in backend/chroma_db, so your documents
    survive restarts.

IMPORTANT POINTS
    * We create the collection with cosine distance:  hnsw:space = cosine.
    * Chroma returns DISTANCE (0 = identical). We convert to SIMILARITY:
          similarity = 1 - distance      (1 = identical, 0 = unrelated)
    * Metadata values must be str / int / float / bool (no None, no lists).
"""

import uuid
from typing import Dict, List

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import settings

# One persistent client for the whole program (created when the file is imported).
_client = chromadb.PersistentClient(
    path=str(settings.CHROMA_DIR),
    settings=ChromaSettings(anonymized_telemetry=False),  # no usage reporting
)


def _collection():
    """Get the collection, creating it the first time."""
    return _client.get_or_create_collection(
        name=settings.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def count() -> int:
    """How many chunks are stored in total."""
    return _collection().count()


def add_chunks(chunks: List[Dict], embeddings: List[List[float]]) -> None:
    """
    Store chunks together with their embeddings.

    Each chunk dict must contain: text, source, page, chunk_index.
    Old chunks of the same file are removed first, so uploading the same
    file twice does not create duplicates.
    """
    col = _collection()
    if not chunks:
        return
    col.delete(where={"source": chunks[0]["source"]})
    col.add(
        ids=[f"{c['source']}-{c['chunk_index']}-{uuid.uuid4().hex[:8]}" for c in chunks],
        documents=[c["text"] for c in chunks],
        embeddings=embeddings,
        metadatas=[
            {"source": c["source"], "page": int(c["page"]), "chunk_index": int(c["chunk_index"])}
            for c in chunks
        ],
    )


def search(query_embedding: List[float], k: int = 4) -> List[Dict]:
    """
    Return the k most similar chunks, best first.
    Each result: {text, source, page, chunk_index, score}   (score = similarity)
    """
    col = _collection()
    total = col.count()
    if total == 0:
        return []
    res = col.query(
        query_embeddings=[query_embedding],
        n_results=min(k, total),          # asking for more than exist raises an error
        include=["documents", "metadatas", "distances"],
    )
    results = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        results.append({**meta, "text": text, "score": round(1 - float(dist), 4)})
    return results


def get_all_chunks() -> List[Dict]:
    """
    Every stored chunk in reading order (file name, then position in file).
    Used by 'spread retrieval' for summaries.
    """
    col = _collection()
    if col.count() == 0:
        return []
    res = col.get(include=["documents", "metadatas"])
    items = [{**m, "text": t} for t, m in zip(res["documents"], res["metadatas"])]
    items.sort(key=lambda c: (c["source"], c["chunk_index"]))
    return items


def list_sources() -> List[Dict]:
    """[{name, chunks}] - one entry per uploaded file."""
    counts: Dict[str, int] = {}
    for c in get_all_chunks():
        counts[c["source"]] = counts.get(c["source"], 0) + 1
    return [{"name": n, "chunks": k} for n, k in sorted(counts.items())]


def delete_source(name: str) -> None:
    """Remove every chunk that came from one file."""
    _collection().delete(where={"source": name})
