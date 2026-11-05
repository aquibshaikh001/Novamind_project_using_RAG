"""
services/ingestion.py  -  turns an uploaded file into searchable knowledge.

WHY THIS FILE EXISTS
    An AI model cannot read a 100-page PDF in one go, and a vector database
    cannot search "a whole PDF". So we do the classic RAG preparation:

        FILE  ->  extract text per page  ->  cut into small CHUNKS
              ->  embed every chunk      ->  store in ChromaDB

    This file does the whole pipeline in the function `ingest_file()`.
"""

from pathlib import Path
from typing import Dict, List, Tuple

from pypdf import PdfReader

from config import settings
from services import ollama_client, vector_store

# File types we accept. Anything else is rejected by routers/documents.py.
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


# ----------------------------------------------------------------------
# STEP 1 - read the file and get text together with its page number
# ----------------------------------------------------------------------
def load_pages(path: Path) -> List[Tuple[int, str]]:
    """
    Return a list of (page_number, text). Page numbers start at 1.
    Plain text files have no pages, so everything is "page 1".
    """
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""   # scanned pages give None -> ""
            pages.append((number, text))
        return pages

    # .txt and .md - errors="ignore" skips characters that cannot be decoded
    return [(1, path.read_text(encoding="utf-8", errors="ignore"))]


# ----------------------------------------------------------------------
# STEP 2 - cut long text into overlapping chunks
# ----------------------------------------------------------------------
def split_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    Cut `text` into pieces of about `chunk_size` characters.

    WHY OVERLAP?
        Consecutive chunks share `overlap` characters. If an important
        sentence sits on a boundary, it still appears whole in one chunk.

    WHY TRY TO CUT AT A SPACE / FULL STOP?
        Cutting in the middle of a word makes poor embeddings. We look
        backwards (in the last 40% of the window) for ". " or " " and cut there.

    IMPORTANT: the loop always moves forward (start increases), so it can
    never run forever.
    """
    text = " ".join(text.split())          # collapse newlines/tabs/double spaces
    chunks: List[str] = []
    start, length = 0, len(text)

    while start < length:
        end = min(start + chunk_size, length)

        if end < length:                    # not the last chunk -> find a nice cut
            window_start = start + int(chunk_size * 0.6)
            cut = max(text.rfind(". ", window_start, end), text.rfind(" ", window_start, end))
            if cut != -1:
                end = cut + 1

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= length:
            break
        start = max(end - overlap, start + 1)   # step back by `overlap`, but always progress

    return chunks


# ----------------------------------------------------------------------
# STEP 3 - the full pipeline
# ----------------------------------------------------------------------
def ingest_file(path: Path) -> Dict:
    """
    Read -> chunk -> embed -> store. Returns a small report for the UI.
    Raises ValueError if the file contains no readable text.
    """
    filename = path.name
    chunks: List[Dict] = []

    for page_number, page_text in load_pages(path):
        for piece in split_text(page_text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP):
            chunks.append(
                {
                    "text": piece,
                    "source": filename,
                    "page": page_number,
                    "chunk_index": len(chunks),   # position in the whole file
                }
            )

    if not chunks:
        raise ValueError(
            "No readable text found. If this is a scanned PDF (images only), "
            "it needs OCR first."
        )

    # Embed in batches of 32 so one request is never too large.
    embeddings: List[List[float]] = []
    for i in range(0, len(chunks), 32):
        batch = [c["text"] for c in chunks[i : i + 32]]
        embeddings.extend(ollama_client.embed(batch))

    vector_store.add_chunks(chunks, embeddings)
    return {"filename": filename, "chunks": len(chunks)}
